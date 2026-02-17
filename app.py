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
        .stTabs [data-baseweb="tab-list"] { gap: 2px; }
        .stTabs [data-baseweb="tab"] { padding-right: 8px; padding-left: 8px; white-space: nowrap; }
        .tab-desc { font-size: 0.85rem; color: #555; margin-bottom: 15px; }
        .filter-badge { background-color: #e3f2fd; color: #0d47a1; padding: 3px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 3. BULLETPROOF DATA FETCHING & FILTERING ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_news_cached(query, max_results=30):
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
            # We only want to display top 15, but we fetch more initially since we filter some out
            if len(articles) >= 15:
                break
                
            title_el = item.find('title')
            link_el = item.find('link')
            pub_date_el = item.find('pubDate')
            
            raw_title = title_el.text if title_el is not None and title_el.text else "No Title"
            link = link_el.text if link_el is not None and link_el.text else "#"
            pub_date_raw = pub_date_el.text if pub_date_el is not None and pub_date_el.text else ""
            
            # --- 14-DAY STRICT PYTHON FILTER ---
            if pub_date_raw:
                try:
                    dt = email.utils.parsedate_to_datetime(pub_date_raw)
                    # Force timezone awareness to compare safely
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                    
                    # If the article is older than 14 days, skip it entirely
                    if dt < cutoff_date:
                        continue 
                        
                    date_str = dt.strftime("%b %d, %Y")
                except Exception:
                    # If date parsing fails, fallback to raw string
                    date_str = pub_date_raw[:16] 
            else:
                date_str = "Recent"
            
            clean_title = html.unescape(raw_title).replace("[", "(").replace("]", ")")
            
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

def get_news(query):
    with st.spinner("Scanning industry sources (Past 14 Days)..."):
        return fetch_news_cached(query)

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

# --- 4. APP UI ---
st.title("🚛 Michelin B2B Fleet Radar")
st.markdown("**Market Intelligence:** Class 3-8 commercial fleets & commercial tire dealers.")
st.markdown(f"<div class='time-stamp'>Last synced: {datetime.now().strftime('%I:%M %p')} <span class='filter-badge'>🗓️ Past 14 Days</span></div>", unsafe_allow_html=True)

# Broadened core keywords for higher catch-rate
core_keywords = '("trucking" OR "fleet" OR "freight" OR "logistics" OR "commercial tire" OR "truck tire")'

tab1, tab2, tab3, tab4 = st.tabs([
    "🤝 M&A", 
    "🚨 Struggles", 
    "👔 Leaders", 
    "🗺️ Strategy"
])

with tab1:
    st.subheader("Mergers & Acquisitions")
    st.markdown("<div class='tab-desc'>Consolidations, buyouts, and acquisitions reported in the last 2 weeks.</div>", unsafe_allow_html=True)
    # Loosened M&A terms
    query = f'{core_keywords} AND ("merger" OR "acquisition" OR "acquires" OR "buyout" OR "sold" OR "consolidation")'
    display_articles(get_news(query))

with tab2:
    st.subheader("Business Struggles")
    st.markdown("<div class='tab-desc'>Recent loan defaults, bankruptcies, closures, layoffs, and liquidations.</div>", unsafe_allow_html=True)
    # Loosened negative business terms
    query = f'{core_keywords} AND ("bankruptcy" OR "chapter 11" OR "closes" OR "layoff" OR "liquidation" OR "debt" OR "default" OR "struggle")'
    display_articles(get_news(query))

with tab3:
    st.subheader("Leadership Changes")
    st.markdown("<div class='tab-desc'>Recent executive swaps, new CEOs, and management shifts.</div>", unsafe_allow_html=True)
    # Broadened executive terms
    query = f'{core_keywords} AND ("CEO" OR "executive" OR "president" OR "leadership" OR "management")'
    display_articles(get_news(query))

with tab4:
    st.subheader("Strategy & Footprint")
    st.markdown("<div class='tab-desc'>Recent location openings, facility expansions, and strategic shifts.</div>", unsafe_allow_html=True)
    # Broadened real estate and footprint keywords
    query = f'{core_keywords} AND ("opens" OR "expands" OR "new location" OR "facility" OR "relocates" OR "closes" OR "expansion" OR "terminal")'
    display_articles(get_news(query))

st.divider()
if st.button("🔄 Refresh Market Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
