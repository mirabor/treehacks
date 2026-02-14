import streamlit as st
import os
import json
import math
import uuid
import time
from dotenv import load_dotenv
from openai import OpenAI
from kalshi_helper import KalshiClient

# Load environment variables
load_dotenv()

# Initialize OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Kalshi Client
try:
    kalshi = KalshiClient()
    st.sidebar.success("Kalshi API Connected")
except Exception as e:
    st.sidebar.error(f"Kalshi Connection Error: {e}")
    kalshi = None

def get_ai_portfolio(thesis, events):
    """
    Uses OpenAI to analyze events and generate a portfolio based on the thesis.
    """
    # Filter events to a manageable size for prompt, maybe just titles and tickers
    # To avoid hitting token limits, let's take the first 50-100 events or summary
    # For this hackathon scope, let's assume raw list is okay but we should format it.
    
    events_summary = []
    for event in events.get('events', [])[:60]: # Limit to 60 events to be safe with context
        events_summary.append({
            "ticker": event.get('ticker'),
            "title": event.get('title'),
            "markets": [m.get('ticker') for m in event.get('markets', [])] # Markets are the actual tradeable contracts
        })
    
    prompt = f"""
    You are a prediction market analyst. 
    Trend Thesis: "{thesis}"
    
    Available Events (subset):
    {json.dumps(events_summary)}
    
    Task: Select the top 5 most correlated market tickers that align with the thesis.
    If the thesis is bearish, choose 'no' for positive outcomes/milestones. 
    If bullish, choose 'yes'.
    
    Strictly return a JSON object with this format:
    {{
        "theme": "Short descriptive theme name",
        "orders": [
            {{"ticker": "MARKET_TICKER", "side": "yes" or "no", "weight": 0.2}}
        ]
    }}
    The weights should sum to 1.0.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful financial analyst assistant."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    content = response.choices[0].message.content
    return json.loads(content)

def calculate_orders(portfolio, budget, prices_map):
    """
    Calculates number of contracts to buy based on budget and weights.
    Returns a list of order payloads and total estimated cost.
    """
    orders_to_execute = []
    total_spend = 0
    
    for item in portfolio.get('orders', []):
        ticker = item['ticker']
        side = item['side']
        weight = item['weight']
        
        # Get price for the specific side
        # Default to 99 cents if unknown to be conservative on budget
        # (buying at 99c means we get fewer contracts than if price was 50c)
        price_dict = prices_map.get(ticker, {})
        if side == 'yes':
            price = price_dict.get('yes', 99)
        else:
            price = price_dict.get('no', 99)
            
        if not price or price <= 0:
            price = 99 # Fallback
        
        allocated_amount = budget * weight
        # allocated is in dollars, price is in cents.
        # contracts = (dollars * 100) / cents
        num_contracts = math.floor((allocated_amount * 100) / price)
        
        if num_contracts > 0:
            orders_to_execute.append({
                "ticker": ticker,
                "side": side,
                "count": num_contracts,
                "type": "market",
                "client_order_id": str(uuid.uuid4()),
                "action": "buy"
            })
            total_spend += num_contracts * (price / 100)
            
    return orders_to_execute, total_spend

st.title("Kalshi ETFs")
st.subheader("Thematic ETF Engine for Kalshi")

thesis = st.text_area("Enter your Trend Thesis", "AI Stagnation in 2025")
budget = st.number_input("Budget ($)", min_value=1.0, value=10.0, step=1.0)

if st.button("Generate ETF"):
    if not kalshi:
        st.error("Kalshi API not connected. Check keys.")
    else:
        with st.spinner("Fetching Events from Kalshi..."):
            events_data = kalshi.get_open_events(limit=100)
            
            if "error" in events_data:
                st.error(f"Failed to fetch events: {events_data['error']}")
            else:
                st.success(f"Fetched {len(events_data.get('events', []))} events.")
                
                with st.spinner("AI Analyzing markets..."):
                    portfolio = get_ai_portfolio(thesis, events_data)
                    st.session_state['portfolio'] = portfolio
                    st.session_state['events_data'] = events_data # Store for price lookup
                
if 'portfolio' in st.session_state:
    portfolio = st.session_state['portfolio']
    st.info(f"Generated Theme: **{portfolio.get('theme', 'Unknown')}**")
    
    # Display simplified table
    st.table(portfolio.get('orders', []))
    
    if st.button("Execute Trade"):
        # Create a price map from the stored event data
        prices_map = {}
        events_data = st.session_state.get('events_data', {})
        
        # Attempt to extract prices. 
        # Note: If /events doesn't return 'yes_ask'/'no_ask', this will need 
        # a separate fetch strategy (e.g. kalshi.get_market(ticker)).
        # For now, we rely on the events data structure having markets.
        for event in events_data.get('events', []):
            for market in event.get('markets', []):
                m_ticker = market.get('ticker')
                prices_map[m_ticker] = {
                    'yes': market.get('yes_ask'),
                    'no': market.get('no_ask')
                }
        
        final_orders, total_estimated_cost = calculate_orders(portfolio, budget, prices_map)
        
        if not final_orders:
            st.warning("No valid orders generated. Check budget or market prices.")
        else:
            st.write(f"Executing {len(final_orders)} orders...")
            st.write(f"Estimated Cost: ${total_estimated_cost:.2f}")
            
            # Split into batches of 20
            batch_size = 20
            for i in range(0, len(final_orders), batch_size):
                batch = final_orders[i:i+batch_size]
                try:
                    response = kalshi.submit_batch_orders(batch)
                    st.success(f"Batch {i//batch_size + 1} Submitted")
                    st.json(response)
                except Exception as e:
                    st.error(f"Batch {i//batch_size + 1} Failed: {e}")
                    
            st.success("Execution Process Complete!")
