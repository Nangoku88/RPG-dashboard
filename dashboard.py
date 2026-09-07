# -*- coding: utf-8 -*-
import time
import sys
import requests
import streamlit as st
# 6行目あたり
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
from plyer import notification
from datetime import datetime

# Windows環境での文字化け防止
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# ページの設定
st.set_page_config(
    page_title="AntiGravity RPG Control Room",
    page_icon="🦅",
    layout="wide"
)

# === セッション状態の初期化 ===
if "logs" not in st.session_state:
    st.session_state.logs = []
if "last_price" not in st.session_state:
    st.session_state.last_price = 154.500
if "price_trend" not in st.session_state:
    st.session_state.price_trend = "flat"
if "flash_active" not in st.session_state:
    st.session_state.flash_active = False
if "last_alert_time" not in st.session_state:
    st.session_state.last_alert_time = 0
if "is_emergency" not in st.session_state:
    st.session_state.is_emergency = False
if "last_m1_time" not in st.session_state:
    st.session_state.last_m1_time = 0

# === サイドバーコントロール ===
with st.sidebar:
    st.header("⚙️ 司令室コントロール")
    night_mode = st.checkbox("🌙 深夜モード（消音）", value=True, key="night_mode_checkbox")
    st.markdown("---")
    st.markdown("🛡️ **戦闘部隊ステータス (7名)**")
    st.markdown("👑 **グラビティ**: 司令塔")
    st.markdown("🦅 **ファルコン**: ニュース")
    st.markdown("🎯 **スナイパー**: 板・オーダー")
    st.markdown("⏳ **オラクル**: 経済指標・時間")
    st.markdown("📈 **レーダー**: 1分足高安")
    st.markdown("📅 **クロノス**: 152円・窓")
    st.markdown("💓 **センチネル**: 死活監視")

# === カスタムCSS ===
st.markdown("""
<style>
    .stApp > header:nth-child(1) {display: none;}
    .block-container {padding-top: 1.5rem; padding-bottom: 1rem;}
    
    .rpg-card {
        background-color: #161b22;
        border: 2px solid #30363d;
        border-radius: 10px;
        padding: 8px;
        text-align: center;
        box-shadow: 0 3px 5px rgba(0,0,0,0.3);
        height: 215px;
        margin-bottom: 10px;
    }
    .empty-slot {
        background-color: #0d1117;
        border: 1px dashed #30363d;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        height: 215px;
        color: #484f58;
        font-size: 0.75rem;
        margin-bottom: 10px;
    }
    
    @keyframes price-up-heavy {
        0% { border-color: #30363d; background-color: #161b22; }
        20% { border-color: #ff3333; background-color: #591212; box-shadow: 0 0 35px rgba(255,51,51,0.9); }
        100% { border-color: #30363d; background-color: #161b22; }
    }
    .flash-up {animation: price-up-heavy 1.5s ease-in-out;}

    @keyframes price-down-heavy {
        0% { border-color: #30363d; background-color: #161b22; }
        20% { border-color: #1f6feb; background-color: #113359; box-shadow: 0 0 35px rgba(31,111,235,0.9); }
        100% { border-color: #30363d; background-color: #161b22; }
    }
    .flash-down {animation: price-down-heavy 1.5s ease-in-out;}

    @keyframes global-siren {
        0% { background-color: #0e1117; }
        50% { background-color: #3d0a0a; box-shadow: inset 0 0 80px rgba(255,0,0,0.6); }
        100% { background-color: #0e1117; }
    }
    .emergency-alarm-bg {animation: global-siren 0.8s infinite ease-in-out; border: 2px solid #ff3333 !important;}

    @keyframes bounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-4px); }
    }
    .pixel-avatar {font-size: 1.4rem; animation: bounce 1.5s infinite ease-in-out; display: inline-block; margin-bottom: 0px;}
    
    .dialogue-box {
        background-color: #0d1117;
        border: 1px dashed #00ffcc;
        border-radius: 6px;
        padding: 6px;
        font-size: 0.76rem;
        color: #e6edf3;
        margin-top: 4px;
        min-height: 60px;
        text-align: left;
        overflow-y: auto;
        line-height: 1.3;
    }
    .status-badge {font-size: 0.65rem; padding: 1px 5px; border-radius: 4px; background-color: #238636; color: white; font-weight: bold;}
    .log-box-right {background-color: #0d1117; border: 2px solid #1f6feb; border-radius: 10px; padding: 10px; height: 435px; overflow-y: auto; font-family: monospace; font-size: 0.8rem; color: #c9d1d9; text-align: left; box-shadow: 0 0 10px rgba(31,111,235,0.2);}
    
    .session-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: bold;
        margin: 0 4px;
    }
    .session-active {
        background-color: #238636;
        color: #ffffff;
        box-shadow: 0 0 6px rgba(35,134,54,0.6);
    }
    .session-closed {
        background-color: #21262d;
        color: #484f58;
    }
</style>
""", unsafe_allow_html=True)

# === 市場セッション判定ロジック（JST基準） ===
now_jst = datetime.now()
current_hour = now_jst.hour
current_minute = now_jst.minute

tokyo_active = 9 <= current_hour < 15
london_active = (16 <= current_hour) or (current_hour < 2)
ny_active = (22 <= current_hour) or (current_hour < 7)

tokyo_class = "session-active" if tokyo_active else "session-closed"
london_class = "session-active" if london_active else "session-closed"
ny_class = "session-active" if ny_active else "session-closed"

# === 時計エリア ===
current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
st.markdown(f"<h2 style='text-align: center; color: #ffcc00; font-family: monospace; margin-top: 10px; margin-bottom: 4px;'>⏰ 現在時刻: {current_time_str}</h2>", unsafe_allow_html=True)

st.markdown(f"""
<div style="text-align: center; margin-bottom: 15px;">
    <span class="session-badge {tokyo_class}">🇯🇵 東京</span>
    <span class="session-badge {london_class}">🇬🇧 ロンドン</span>
    <span class="session-badge {ny_class}">🇺🇸 ニューヨーク</span>
</div>
""", unsafe_allow_html=True)

# === 設定エリア ===
LINE_ACCESS_TOKEN = "ROOwK38JJPiBxX73b55xK0V3dy0yAt5gVQ6zcBkMDkrFTClPOzC/5pmd/jkO2BfCC3HsI7m4FeqZNmr9/Pwxy2c2VRwkygDycJeWhLpkm3tkNfVDyECwJXXoZLH/PoZ+Z+IDjSWUtc0NwlAx3WYKuwdB04t89/1O/w1cDnyilFU="
LINE_USER_ID = "U38ad9922c0e6b716fb09f62fa2c5ed98"
SYMBOL = "USDJPY"
PIP_VALUE = 0.01

# 通知関数
def send_desktop_popup(title, message):
    try:
        notification.notify(title=title, message=message, app_name='AntiGravity System', timeout=5)
    except Exception as e:
        print(f"[PC通知エラー] {e}")

# === MT5接続チェックとデータ取得 ===
if 'mt5' in globals() and mt5:
    if not mt5.initialize():
        st.error("❌ MT5の初期化に失敗しました。MetaTrader 5が起動しているか確認してください。")
        tick = None
        d1_rates = []
        m1_rates = []
    else:
        tick = mt5.symbol_info_tick(SYMBOL)
        d1_rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_D1, 0, 1)
        m1_rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, 1)

today_open = d1_rates[0]['open'] if d1_rates is not None and len(d1_rates) > 0 else 0.0
today_low = d1_rates[0]['low'] if d1_rates is not None and len(d1_rates) > 0 else 0.0
today_high = d1_rates[0]['high'] if d1_rates is not None and len(d1_rates) > 0 else 0.0

m1_high = m1_rates[0]['high'] if m1_rates is not None and len(m1_rates) > 0 else 0.0
m1_low = m1_rates[0]['low'] if m1_rates is not None and len(m1_rates) > 0 else 0.0
m1_time = m1_rates[0]['time'] if m1_rates is not None and len(m1_rates) > 0 else 0.0
m1_range_pips = (m1_high - m1_low) / PIP_VALUE if PIP_VALUE > 0 else 0.0

    if tick:
        current_price = tick.bid
        
        price_diff = current_price - st.session_state.last_price
        pips_diff = abs(price_diff) / PIP_VALUE
        
        if pips_diff >= 3.0:
            if price_diff > 0:
                st.session_state.price_trend = "up"
            else:
                st.session_state.price_trend = "down"
            st.session_state.flash_active = True
            st.session_state.last_price = current_price
        else:
            st.session_state.flash_active = False
            if current_price != st.session_state.last_price:
                st.session_state.last_price = current_price
        
        today_diff = current_price - today_open
        today_pips = today_diff / PIP_VALUE

        current_time = time.time()
        if m1_range_pips >= 15 and (m1_time != st.session_state.last_m1_time or (current_time - st.session_state.last_alert_time) > 40):
            st.session_state.is_emergency = True
            is_30 = m1_range_pips >= 30
            
            alert_type = "【⚠️ 1分足30pips超・モンスター変動】" if is_30 else "【⚡ 1分足高安15pips急変】"
            msg_text = f"1分足の急加速を検知！\n📈 高安レンジ: 約 {m1_range_pips:.1f} pips\n最高: {m1_high} ➡ 最安: {m1_low} (現在: {current_price})"

            title = f"AntiGravity 速報 {alert_type}"
            send_desktop_popup(title, msg_text)
            
            if not night_mode:
                st.markdown('<audio autoplay="true"><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>', unsafe_allow_html=True)
            
            log_msg = f"[{time.strftime('%H:%M:%S')}] 🚨 1分足急変！高安差 {m1_range_pips:.1f} pips (current: {current_price})"
            if len(st.session_state.logs) == 0 or st.session_state.logs[0] != log_msg:
                st.session_state.logs.insert(0, log_msg)
                
            st.session_state.last_alert_time = current_time
            st.session_state.last_m1_time = m1_time

        if st.session_state.is_emergency and (current_time - st.session_state.last_alert_time > 60):
            st.session_state.is_emergency = False

        # --- 各エージェントの動的セリフ構築 ---
        if m1_range_pips >= 15:
            gravity_dialogue = f"〈緊急！M1高安差{m1_range_pips:.1f}pips突破！全軍、スキャル迎撃態勢！〉"
            sniper_dialogue = "<span>指値の厚い壁が破られた！ブレイク方向へ強襲する！</span>"
            oracle_dialogue = "<span>警告：ボラティリティ急増中！時間軸のノイズに惑わされるな！</span>"
        elif m1_range_pips >= 10:
            gravity_dialogue = "〈値動きが活発化してきたぞ。板の厚さに全神経を集中しろ。〉"
            sniper_dialogue = "<span>上下のオーダーフロー拮抗中。次の大口の仕掛けをロックオン。</span>"
            oracle_dialogue = f"<span>現在分速 {current_minute}分。次のクローズアワーに向け警戒レベル引上。</span>"
        else:
            gravity_dialogue = "〈ボス、マルチ口座の連携は順調だ。冷静に好機を待て。〉"
            sniper_dialogue = "<span>スプレッド安定。主要な指値板に目立った偏りなし。</span>"
            oracle_dialogue = f"<span>時間監視正常。次の重要指標までポジションを管理せよ。</span>"

        if ny_active:
            falcon_dialogue = "<span>NY市場リアルタイム監視：米金利と要人発言のフローを全スキャン中。</span>"
        elif london_active:
            falcon_dialogue = "<span>ロンドン勢参入：欧州アタックのトレンド発生をマーク中。</span>"
        else:
            falcon_dialogue = "<span>東京アジアンタイム：手堅いレンジと実需の動きを監視中。</span>"

        chronos_dialogue = f"〈152.00円の攻防および148円台の窓。現在値との乖離: <b>{abs(152.00 - current_price):.2f}円</b>〉"

        card_bg_class = "emergency-alarm-bg" if st.session_state.is_emergency else ""
        
        trend_class = ""
        if st.session_state.flash_active:
            if st.session_state.price_trend == "up":
                trend_class = "flash-up"
            elif st.session_state.price_trend == "down":
                trend_class = "flash-down"

        # --- 上段：5大指標表示 ---
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown(f"""
                <div class="rpg-card {trend_class} {card_bg_class}" style="padding: 12px; text-align: left; height: auto;">
                    <div style="font-size:0.8rem; color:#8b949e; margin-bottom: 2px;">USD/JPY 現在値 (Bid)</div>
                    <div style="font-size:2.3rem; font-weight:bold; color: #ffffff; line-height: 1.2;">{current_price:.3f} 円</div>
                    <div style="margin-top: 6px;"><span style="font-size:0.75rem; color:#238636; background:#113322; padding:2px 6px; border-radius:4px;">1分足高安: {m1_range_pips:.1f}pips</span></div>
                </div>
            """, unsafe_allow_html=True)
            
        col2.metric(label="📊 当日の変動幅 (始値比)", value=f"{today_pips:+.1f} pips", delta=f"始値: {today_open:.3f}")
        col3.metric(label="🎯 ターゲット1 (当日安値)", value=f"{today_low:.3f} 円", delta=f"高値: {today_high:.3f}")
        col4.metric(label="🎯 ターゲット2", value="152.000 円", delta="日足目立った安値")
        col5.metric(label="🎯 ターゲット3", value="148.00-149.00", delta="日足窓埋めライン")

        st.markdown("---", unsafe_allow_html=True)

        # --- 中段：左側に「7人部隊ライブオフィス」、右側に「アラートログ」 ---
        left_col, right_col = st.columns([3.0, 1])

        with left_col:
            st.markdown('<p style="font-size:1.2rem; font-weight:bold; color:#c9d1d9; margin-bottom:10px;">🕹️ 7人戦闘部隊・リアルタイム稼働オフィス</p>', unsafe_allow_html=True)
            
            gravity_card_class = "rpg-card siren-alert" if st.session_state.is_emergency else "rpg-card"
            sentinel_msg = "〈消音監視中：安全航行保持〉" if night_mode else "〈警告音全開放：臨戦態勢〉"

            # --- 【上段 5人】 ---
            r1_cols = st.columns(5)
            
            with r1_cols[0]:
                st.markdown(f"""
                    <div class="{gravity_card_class}">
                        <div class="pixel-avatar">👑</div>
                        <div style="font-size:0.8rem; font-weight:bold;">グラビティ</div>
                        <span class="status-badge">司令塔</span>
                        <div class="dialogue-box">{gravity_dialogue}</div>
                    </div>
                """, unsafe_allow_html=True)
                
            with r1_cols[1]:
                st.markdown(f"""
                    <div class="rpg-card">
                        <div class="pixel-avatar">🦅</div>
                        <div style="font-size:0.8rem; font-weight:bold;">ファルコン</div>
                        <span class="status-badge" style="background-color:#1f6feb;">ニュース</span>
                        <div class="dialogue-box">{falcon_dialogue}</div>
                    </div>
                """, unsafe_allow_html=True)

            with r1_cols[2]:
                st.markdown(f"""
                    <div class="rpg-card">
                        <div class="pixel-avatar">🎯</div>
                        <div style="font-size:0.8rem; font-weight:bold;">スナイパー</div>
                        <span class="status-badge" style="background-color:#d73a49;">板・オーダー</span>
                        <div class="dialogue-box">{sniper_dialogue}</div>
                    </div>
                """, unsafe_allow_html=True)

            with r1_cols[3]:
                st.markdown(f"""
                    <div class="rpg-card">
                        <div class="pixel-avatar">⏳</div>
                        <div style="font-size:0.8rem; font-weight:bold;">オラクル</div>
                        <span class="status-badge" style="background-color:#6f42c1;">時間・指標</span>
                        <div class="dialogue-box">{oracle_dialogue}</div>
                    </div>
                """, unsafe_allow_html=True)
                
            with r1_cols[4]:
                st.markdown(f"""
                    <div class="rpg-card">
                        <div class="pixel-avatar">📈</div>
                        <div style="font-size:0.8rem; font-weight:bold;">レーダー</div>
                        <span class="status-badge" style="background-color:#9e6a03;">価格監視</span>
                        <div class="dialogue-box">M1高安差<br><b>{m1_range_pips:.1f} pips</b></div>
                    </div>
                """, unsafe_allow_html=True)

            # --- 【下段 5枠】 ---
            r2_cols = st.columns(5)
            
            with r2_cols[0]:
                st.markdown(f"""
                    <div class="rpg-card">
                        <div class="pixel-avatar">📅</div>
                        <div style="font-size:0.8rem; font-weight:bold;">クロノス</div>
                        <span class="status-badge" style="background-color:#8957e5;">アナリスト</span>
                        <div class="dialogue-box">{chronos_dialogue}</div>
                    </div>
                """, unsafe_allow_html=True)

            with r2_cols[1]:
                st.markdown(f"""
                    <div class="rpg-card">
                        <div class="pixel-avatar">💓</div>
                        <div style="font-size:0.8rem; font-weight:bold;">センチネル</div>
                        <span class="status-badge" style="background-color:#da3633;">死活監視</span>
                        <div class="dialogue-box">{sentinel_msg}</div>
                    </div>
                """, unsafe_allow_html=True)
                
            with r2_cols[2]:
                st.markdown('<div class="empty-slot"><div>[ 待機スロット ]</div></div>', unsafe_allow_html=True)
                
            with r2_cols[3]:
                st.markdown('<div class="empty-slot"><div>[ 待機スロット ]</div></div>', unsafe_allow_html=True)
                
            with r2_cols[4]:
                st.markdown('<div class="empty-slot"><div>[ 待機スロット ]</div></div>', unsafe_allow_html=True)

        with right_col:
            st.markdown('<p style="font-size:1.2rem; font-weight:bold; color:#c9d1d9; margin-bottom:10px;">🚨 リアルタイム・アラートログ</p>', unsafe_allow_html=True)
            
            unique_logs = []
            for l in st.session_state.logs:
                if l not in unique_logs:
                    unique_logs.append(l)
            st.session_state.logs = unique_logs[:20]
            
            logs_html = "<br>".join(st.session_state.logs)
            st.markdown(f"""
                <div class="log-box-right">
                    {logs_html}
                </div>
            """, unsafe_allow_html=True)

    # 2秒ごとに自動更新
    time.sleep(2)
    st.rerun()