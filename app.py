import streamlit as st
import urllib.parse
import xml.etree.ElementTree as ET
import email.utils
from datetime import datetime, timedelta, timezone
import html
import requests

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Michelin B2B Fleet Radar",
    page_icon="🚛",
    layout="centered",
    initial_sidebar_state="collapsed" 
)

# --- 2. MOBILE CSS STYLING ---
st.markdown("""
    <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 800px;
        }
        a { text-decoration: none; color: #1E88E5; font-weight: 600; }
        a:hover { text-decoration: underline; }
        .time-stamp { font-size: 0.8rem; color: gray; text-align: center; margin-bottom: 1rem; }
        .stTabs [data-baseweb="tab-list"] { gap: 2px; overflow-x: auto; scrollbar-width: none; }
        .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
        .stTabs [data-baseweb="tab"] { padding-right: 8px; padding-left: 8px; white-space: nowrap; }
        .tab-desc { font-size: 0.85rem; color: #555; margin-bottom: 15px; }
        .filter-badge { background-color: #e3f2fd; color: #0d47a1; padding: 3px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 3. BULLETPROOF DATA FETCHING & FILTERING ---
# Added 'title_must_include' parameter (must be a tuple so Streamlit can cache it)
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_news_cached(query, title_must_include=None):
    # Appending when:14d tells Google to only return recent news
    google_query = f"{query} when:14d"
    
    google_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(google_query)}&hl=en-US&gl=US&ceid=US:en"
    bing_url = f"https://www.bing.com/news/search?q={urllib.parse.quote(query)}&format=rss"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }
    
    xml_data = None
    is_google = True
    
    try:
        response = requests.get(google_url, headers=headers, timeout=10)
        response.raise_for_status()
        if b'<rss' not in response.content:
            raise ValueError("Google Block")
        xml_data = response.content
    except Exception:
        try:
            b_response = requests.get(bing_url, headers=headers, timeout=10)
            b_response.raise_for_status()
            xml_data = b_response.content
            is_google = False
        except Exception as e:
            return None, "Failed to load feeds."

    try:
        root = ET.fromstring(xml_data)
        articles = []
        
        # Calculate exactly 14 days ago for strict Python filtering
        now_utc = datetime.now(timezone.utc)
        cutoff_date = now_utc - timedelta(days=14)
        
        for item in root.findall('./channel/item'):
            if len(articles) >= 15:
                break
                
            title_el = item.find('title')
            link_el = item.find('link')
            pub_date_el = item.find('pubDate')
            
            raw_title = title_el.text if title_el is not None and title_el.text else "No Title"
            link = link_el.text if link_el is not None and link_el.text else "#"
            pub_date_raw = pub_date_el.text if pub_date_el is not None and pub_date_el.text else ""
            
            clean_title = html.unescape(raw_title).replace("[", "(").replace("]", ")")
            
            # --- STRICT HEADLINE FILTER (Eliminates noise for recalls) ---
            if title_must_include:
                title_lower = clean_title.lower()
                # If NONE of the required words are in the title, skip this article entirely
                if not any(word in title_lower for word in title_must_include):
                    continue
            
            # --- 14-DAY STRICT PYTHON FILTER ---
            if pub_date_raw:
                try:
                    dt = email.utils.parsedate_to_datetime(pub_date_raw)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                    
                    if dt < cutoff_date:
                        continue 
                        
                    date_str = dt.strftime("%b %d, %Y")
                except Exception:
                    date_str = pub_date_raw[:16] 
            else:
                date_str = "Recent"
            
            source = "Industry News"
            if is_google and " - " in clean_title:
                title_parts = clean_title.rsplit(" - ", 1)
                clean_title = title_parts[0]
                source = title_parts[1]
            elif not is_google:
                source_el = item.find('source')
                if source_el is not None and source_el.text:
                    source = source_el.text
                elif " - " in clean_title:
                    title_parts = clean_title.rsplit(" - ", 1)
                    clean_title = title_parts[0]
                    source = title_parts[1]
                    
            articles.append({
                'title': clean_title.strip(),
                'link': link,
                'date': date_str,
                'source': source.strip()
            })
            
        return articles, None
    except Exception as e:
        return None, str(e)

def get_news(query, title_must_include=None):
    with st.spinner("Scanning industry sources (Past 14 Days)..."):
        return fetch_news_cached(query, title_must_include=title_must_include)

def display_articles(result_tuple):
    articles, error_msg = result_tuple
    if error_msg:
        st.error("⚠️ Failed to load news feed.")
        return
    if not articles:
        st.info("No major events reported in this category in the past 14 days.")
        return
    for article in articles:
        with st.container(border=True):
            st.markdown(f"**[{article['title']}]({article['link']})**")
            st.caption(f"📅 {article['date']} &nbsp;|&nbsp; 🏢 {article['source']}")

# --- 4. APP UI & OPTIMIZED QUERIES ---
st.title("🚛 Michelin B2B Fleet Radar")
st.markdown("**Market Intelligence:** Class 3-8 commercial fleets & commercial tire dealers.")
st.markdown(f"<div class='time-stamp'>Last synced: {datetime.now().strftime('%I:%M %p')} <span class='filter-badge'>🗓️ Past 14 Days</span></div>", unsafe_allow_html=True)

# Centralized search blocks 
BASE_TIRE = '("truck tire" OR "bus tire" OR "truck & bus" OR TBR OR "commercial tire" OR "commercial tyre" OR "on-road tire" OR "on road tire")'
NEGATIVES = '-"Michelin Guide" -restaurant -"tire pressure monitor" -bicycle -motorcycle -"passenger tire" -"passenger tyre" -passenger'

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🆕 Products", 
    "♻️ Retreads", 
    "🛠️ Services", 
    "🏢 Brands",
    "🚚 Class 6-8",
    "⚠️ Recalls",
])

with tab1:
    st.subheader("New Products & Tech")
    st.markdown("<div class='tab-desc'>Tracking line extensions, new sizes, product news, and unveilings.</div>", unsafe_allow_html=True)
    query = f'{BASE_TIRE} AND (launch OR "new product" OR "product news" OR announcement OR "line extension" OR "new size" OR "new range" OR unveiling) {NEGATIVES}'
    display_articles(get_news(query))

with tab2:
    st.subheader("Retreading & Manufacturing")
    st.markdown("<div class='tab-desc'>Investments, new plants, expansions, and casing management programs.</div>", unsafe_allow_html=True)
    query = f'(retread OR remold OR remolds OR recap OR recaps OR "pre-mold" OR "pre mold" OR casing OR casings OR "casing program" OR "casing management" OR "retread plant" OR "tread rubber" OR "tread design") AND {BASE_TIRE} AND (launch OR announcement OR expansion OR investment OR partnership OR "new plant" OR capacity OR "new tread") {NEGATIVES}'
    display_articles(get_news(query))

with tab3:
    st.subheader("Dealers & Services")
    st.markdown("<div class='tab-desc'>Dealerships, mobile networks, roadside service, promotions, and price changes.</div>", unsafe_allow_html=True)
    query = f'{BASE_TIRE} AND (dealer OR dealership OR distributor OR "service network" OR "fleet service" OR "tire service" OR "service program" OR "service offer" OR "mobile service" OR "roadside service" OR "tire management" OR promotion OR rebate OR "price increase") {NEGATIVES}'
    display_articles(get_news(query))

with tab4:
    st.subheader("Competitor Pulse")
    st.markdown("<div class='tab-desc'>Tracking major commercial moves across tier 1 and tier 2 competitors.</div>", unsafe_allow_html=True)
    competitors = '(Bridgestone OR Continental OR Giti OR Goodyear OR Kumho OR Hankook OR Michelin OR Nokian OR Pirelli OR Toyo OR Yokohama OR "General Tire" OR Firestone OR Uniroyal OR Kelly)'
    query = f'{competitors} AND ({BASE_TIRE} OR retread OR recap OR recaps OR casing OR casings) {NEGATIVES}'
    display_articles(get_news(query))

with tab5:
    st.subheader("Class 6-8 & Fleets")
    st.markdown("<div class='tab-desc'>Tracking heavy duty tractor-trailers, line haul, and fleet service programs.</div>", unsafe_allow_html=True)
    class_terms = '("Class 6" OR "Class 7" OR "Class 8" OR "heavy-duty" OR "heavy duty" OR "tractor trailer" OR semi OR "line haul" OR "regional haul" OR "long haul" OR "8x4" OR "6x4")'
    query = f'{class_terms} AND ({BASE_TIRE} OR retread OR recap OR recaps OR casing OR casings) AND (launch OR announcement OR "new product" OR "new line" OR recall OR "service program" OR "fleet service") {NEGATIVES}'
    display_articles(get_news(query))

with tab6:
    st.subheader("Recalls & Safety Alerts")
    st.markdown("<div class='tab-desc'>Strictly filtered for commercial tire defects, tread separations, and NHTSA actions.</div>", unsafe_allow_html=True)
    
    # Layer 1 (API Level): Strip out truck engine components, food, and conversational uses
    vehicle_negatives = '-engine -brakes -steering -airbag -transmission -seatbelt -emissions -food -poultry -meat -politics -"recalls the" -"recalls that" -"recalls how" -"recalls when"'
    query = f'{BASE_TIRE} AND (recall OR recalls OR recalled OR defect OR NHTSA OR "stop sale") {NEGATIVES} {vehicle_negatives}'
    
    # Layer 2 (Python Level): The headline MUST contain one of these safety/recall keywords.
    # Note: Streamlit caching requires this list to be passed as a Tuple (...) rather than a List [...]
    mandatory_title_words = ("recall", "recalled", "recalls", "nhtsa", "defect", "stop sale")
    
    display_articles(get_news(query, title_must_include=mandatory_title_words))

st.divider()
if st.button("🔄 Refresh Market Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
