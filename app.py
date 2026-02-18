import streamlit as st
import urllib.parse
import xml.etree.ElementTree as ET
import email.utils
from datetime import datetime, timedelta, timezone
import html
import requests

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Class 7 & 8 Fleet Radar",
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
            if len(articles) >= 20: 
                break
                
            title_el = item.find('title')
            link_el = item.find('link')
            pub_date_el = item.find('pubDate')
            
            raw_title = title_el.text if title_el is not None and title_el.text else "No Title"
            link = link_el.text if link_el is not None and link_el.text else "#"
            pub_date_raw = pub_date_el.text if pub_date_el is not None and pub_date_el.text else ""
            
            clean_title = html.unescape(raw_title).replace("[", "(").replace("]", ")")
            
            # --- STRICT HEADLINE FILTER ---
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
st.title("🚛 Class 7 & 8 Fleet Radar")
st.markdown("**Executive Market Intelligence:** Heavy-duty fleets, OEMs, M&A, and Tire Suppliers.")
st.markdown(f"<div class='time-stamp'>Last synced: {datetime.now().strftime('%I:%M %p')} <span class='filter-badge'>🗓️ Past 14 Days</span></div>", unsafe_allow_html=True)

# Broad negatives to keep consumer vehicles and unrelated industries out of B2B results
NEGATIVES = '-passenger -car -cars -pickup -suv -auto -airline -airlines -motorcycle -bicycle -restaurant -"Michelin Guide" -food'

tab1, tab2, tab3, tab4 = st.tabs([
    "🚚 Class 7 & 8 Fleets",
    "🤝 M&A / Bankruptcies", 
    "🏭 Class 8 OEMs", 
    "🛞 Tire Suppliers" 
])

with tab1:
    st.subheader("Class 7 & 8 Fleet News")
    st.markdown("<div class='tab-desc'>General market news on heavy-duty truck fleets, operations, and freight trends.</div>", unsafe_allow_html=True)
    
    # Query: Heavy-duty terms intersected with fleet operational terms
    query = f'("Class 8" OR "Class 7" OR "heavy-duty" OR "heavy duty" OR "semi-truck" OR "tractor trailer") AND ("fleet" OR "fleets" OR "trucking" OR "carrier" OR "carriers") {NEGATIVES}'
    
    display_articles(get_news(query))

with tab2:
    st.subheader("Fleet M&A & Bankruptcies")
    st.markdown("<div class='tab-desc'>Tracking acquisitions, buyouts, closures, and Chapter 11 filings for trucking companies.</div>", unsafe_allow_html=True)
    
    # Query: Carrier/Fleet keywords intersected with financial event keywords
    query = f'("trucking" OR "fleet" OR "freight" OR "motor carrier" OR "logistics" OR "LTL") AND ("merger" OR "acquisition" OR "buyout" OR "acquires" OR "bankruptcy" OR "bankrupt" OR "chapter 11" OR "shuts down" OR "closure" OR "liquidates" OR "sold") {NEGATIVES}'
    
    # We force the headline to contain a business-event word to prevent random articles that just mention the word "bankrupt" in passing
    mandatory_title_words = ("merger", "merges", "acquire", "acquires", "acquisition", "buyout", "bankrupt", "bankruptcy", "chapter 11", "closes", "closure", "shuts down", "shut down", "liquidation", "liquidates", "insolvent", "sold")
    display_articles(get_news(query, title_must_include=mandatory_title_words))

with tab3:
    st.subheader("Class 8 Truck Manufacturers")
    st.markdown("<div class='tab-desc'>News regarding heavy-duty truck production, earnings, and OEM updates.</div>", unsafe_allow_html=True)
    
    # Query: Explicitly target the major North American heavy-duty truck builders
    oems = '("Freightliner" OR "Peterbilt" OR "Kenworth" OR "Volvo Trucks" OR "Mack Trucks" OR "Navistar" OR "Paccar" OR "Daimler Truck" OR "International Trucks" OR "Western Star")'
    query = f'{oems} AND ("Class 8" OR "heavy-duty" OR "heavy duty" OR "semi-truck" OR "tractor trailer" OR "truck" OR "OEM") {NEGATIVES}'
    
    display_articles(get_news(query))

with tab4:
    st.subheader("Class 8 Tire Suppliers")
    st.markdown("<div class='tab-desc'>News from major commercial tire brands specifically related to heavy-duty trucks and Class 8.</div>", unsafe_allow_html=True)
    
    # Query: Major tire brands intersected explicitly with heavy-duty/commercial truck terms
    tire_brands = '("Bridgestone" OR "Continental" OR "Giti" OR "Goodyear" OR "Kumho" OR "Hankook" OR "Michelin" OR "Nokian" OR "Pirelli" OR "Toyo" OR "Yokohama" OR "General Tire" OR "Firestone" OR "Uniroyal" OR "Kelly")'
    query = f'{tire_brands} AND ("Class 8" OR "Class 7" OR "heavy-duty" OR "heavy duty" OR "commercial truck" OR "semi-truck" OR "tractor trailer") AND ("tire" OR "tires" OR "retread" OR "retreads") {NEGATIVES}'
    
    display_articles(get_news(query))

st.divider()
if st.button("🔄 Refresh Market Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
