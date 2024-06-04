import requests
import pandas as pd
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import Font, Alignment
import logging
import time
from datetime import datetime
import joblib
from sklearn.linear_model import LinearRegression
import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import plotly.express as px
import unittest
from unittest.mock import patch, MagicMock

# Configuration
URL = "https://prices.runescape.wiki/api/v1/osrs/latest"
logging.basicConfig(filename='osrs_flipping_tool.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')
DATABASE = 'osrs_flipping.db'

# Database setup
conn = sqlite3.connect(DATABASE, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS price_history (Item TEXT, Buy_Price INTEGER, Sell_Price INTEGER, Date TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, phone TEXT, min_profit INTEGER, min_margin REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS transactions (username TEXT, item TEXT, buy_price INTEGER, sell_price INTEGER, date TEXT, profit INTEGER)''')
conn.commit()

# Function to fetch real-time data from RuneScape Wiki API
def fetch_real_time_data():
    response = requests.get(URL)
    data = response.json()
    items = data['data']
    
    rows = []
    for item_id, item_info in items.items():
        rows.append([
            item_info.get('name', ''),
            item_info.get('buy_average', 0),
            item_info.get('sell_average', 0),
            item_info.get('buy_quantity', 0),
            item_info.get('sell_quantity', 0),
            item_info.get('buy_average', 0) - item_info.get('sell_average', 0)
        ])
    
    df = pd.DataFrame(rows, columns=['Item', 'Buy Price', 'Sell Price', 'Buy Quantity', 'Sell Quantity', 'Profit'])
    return df

# Function to clean and validate data
def clean_data(df):
    df = df.dropna()
    df['Buy Price'] = df['Buy Price'].astype(int)
    df['Sell Price'] = df['Sell Price'].astype(int)
    df['Profit'] = df['Sell Price'] - df['Buy Price']
    return df

# Function to analyze data
def analyze_data(df, min_profit=1000, min_margin=5):
    df = df[(df['Profit'] >= min_profit) & ((df['Profit'] / df['Buy Price']) * 100 >= min_margin)]
    df = df.sort_values(by='Profit', ascending=False)
    return df

# Function to save data to Excel
def save_data_to_excel(df, filename='flipping_opportunities.xlsx'):
    wb = Workbook()
    ws = wb.active
    ws.title = "Flipping Opportunities"

    for r in dataframe_to_rows(df, index=False, header=True):
        ws.append(r)
    
    for cell in ws["1:1"]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            if cell.value and len(str(cell.value)) > max_length:
                max_length = len(cell.value)
        ws.column_dimensions[column].width = max_length + 2

    wb.save(filename)
    print(f"Data saved to {filename}")

# Function to log results
def log_results(df, top_n=10):
    top_items = df.head(top_n)
    logging.info("Top Profitable Items for Flipping:")
    for index, row in top_items.iterrows():
        logging.info(f"Item: {row['Item']}, Buy Price: {row['Buy Price']}, Sell Price: {row['Sell Price']}, Profit: {row['Profit']}")

# Function to update historical data
def update_price_history(df):
    df['Date'] = datetime.now().strftime('%Y-%m-%d')
    df.to_sql('price_history', conn, if_exists='append', index=False)

# Function to train and save machine learning model
def train_model():
    df = pd.read_sql('SELECT * FROM price_history', conn)
    if len(df) > 100:
        df['Timestamp'] = pd.to_datetime(df['Date']).astype(int) / 10**9
        X = df[['Timestamp', 'Buy_Price']]
        y = df['Sell_Price']
        model = LinearRegression()
        model.fit(X, y)
        joblib.dump(model, 'price_predictor.pkl')
        print("Model trained and saved.")

# Function to predict prices using the machine learning model
def predict_prices(df):
    if os.path.exists('price_predictor.pkl'):
        model = joblib.load('price_predictor.pkl')
        df['Timestamp'] = datetime.now().timestamp()
        X = df[['Timestamp', 'Buy Price']]
        df['Predicted Sell Price'] = model.predict(X)
    return df

# Function to display data with matplotlib
def display_data(df, top_n=10):
    top_items = df.head(top_n)
    print(f"Top {top_n} Profitable Items for Flipping:")
    print(top_items[['Item', 'Buy Price', 'Sell Price', 'Profit', 'Buy Quantity', 'Sell Quantity']])
    
    plt.figure(figsize=(12, 6))
    plt.barh(top_items['Item'], top_items['Profit'], color='skyblue')
    plt.xlabel('Profit')
    plt.ylabel('Item')
    plt.title('Top Profitable Items for Flipping')
    plt.gca().invert_yaxis()
    plt.show()

# Function to display data with plotly
def display_data_plotly(df, top_n=10):
    top_items = df.head(top_n)
    fig = px.bar(top_items, x='Profit', y='Item', orientation='h', title='Top Profitable Items for Flipping')
    fig.show()

# Function to fetch and process data
def fetch_and_process_data(min_profit=1000, min_margin=5):
    print("Fetching real-time data...")
    df = fetch_real_time_data()
    
    print("Cleaning and validating data...")
    df = clean_data(df)
    
    print("Analyzing data...")
    analyzed_df = analyze_data(df, min_profit, min_margin)
    
    print("Updating price history...")
    update_price_history(df)
    
    print("Training machine learning model...")
    train_model()
    
    print("Predicting future prices...")
    analyzed_df = predict_prices(analyzed_df)
    
    print("Displaying results...")
    display_data_plotly(analyzed_df)
    
    print("Saving results to Excel...")
    save_data_to_excel(analyzed_df)
    
    print("Logging results...")
    log_results(analyzed_df)

    return analyzed_df

# Function to handle user registration
def register_user(username, email, phone, min_profit, min_margin):
    c.execute('INSERT INTO users VALUES (?, ?, ?, ?, ?)', (username, email, phone, min_profit, min_margin))
    conn.commit()

# Function to handle user preferences
def get_user_preferences(username):
    c.execute('SELECT min_profit, min_margin FROM users WHERE username = ?', (username,))
    return c.fetchone()

# Function to handle user transactions
def log_transaction(username, item, buy_price, sell_price, profit):
    c.execute('INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?)', (username, item, buy_price, sell_price, datetime.now().strftime('%Y-%m-%d'), profit))
    conn.commit()

# GUI setup using tkinter
class OSRSFlippingToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OSRS Flipping Tool")
        self.create_widgets()
    
    def create_widgets(self):
        # User registration frame
        self.registration_frame = ttk.LabelFrame(self.root, text="User Registration")
        self.registration_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        ttk.Label(self.registration_frame, text="Username:").grid(row=0, column=0, padx=5, pady=5)
        self.username_entry = ttk.Entry(self.registration_frame)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(self.registration_frame, text="Email:").grid(row=1, column=0, padx=5, pady=5)
        self.email_entry = ttk.Entry(self.registration_frame)
        self.email_entry.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(self.registration_frame, text="Phone:").grid(row=2, column=0, padx=5, pady=5)
        self.phone_entry = ttk.Entry(self.registration_frame)
        self.phone_entry.grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(self.registration_frame, text="Min Profit:").grid(row=3, column=0, padx=5, pady=5)
        self.min_profit_entry = ttk.Entry(self.registration_frame)
        self.min_profit_entry.grid(row=3, column=1, padx=5, pady=5)
        
        ttk.Label(self.registration_frame, text="Min Margin:").grid(row=4, column=0, padx=5, pady=5)
        self.min_margin_entry = ttk.Entry(self.registration_frame)
        self.min_margin_entry.grid(row=4, column=1, padx=5, pady=5)
        
        self.register_button = ttk.Button(self.registration_frame, text="Register", command=self.register_user)
        self.register_button.grid(row=5, column=0, columnspan=2, pady=10)
        
        # Data analysis frame
        self.analysis_frame = ttk.LabelFrame(self.root, text="Data Analysis")
        self.analysis_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        ttk.Label(self.analysis_frame, text="Min Profit:").grid(row=0, column=0, padx=5, pady=5)
        self.analysis_min_profit_entry = ttk.Entry(self.analysis_frame)
        self.analysis_min_profit_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(self.analysis_frame, text="Min Margin:").grid(row=1, column=0, padx=5, pady=5)
        self.analysis_min_margin_entry = ttk.Entry(self.analysis_frame)
        self.analysis_min_margin_entry.grid(row=1, column=1, padx=5, pady=5)
        
        self.analyze_button = ttk.Button(self.analysis_frame, text="Analyze", command=self.analyze_data)
        self.analyze_button.grid(row=2, column=0, columnspan=2, pady=10)
        
        # Results frame
        self.results_frame = ttk.LabelFrame(self.root, text="Results")
        self.results_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        
        self.results_text = tk.Text(self.results_frame, height=15, width=70)
        self.results_text.grid(row=0, column=0, padx=5, pady=5)
        
        self.save_button = ttk.Button(self.results_frame, text="Save to Excel", command=self.save_to_excel)
        self.save_button.grid(row=1, column=0, pady=10)
        
        # Graphical charts frame
        self.charts_frame = ttk.LabelFrame(self.root, text="Graphical Charts")
        self.charts_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        
        self.plotly_button = ttk.Button(self.charts_frame, text="Show Plotly Chart", command=self.show_plotly_chart)
        self.plotly_button.grid(row=0, column=0, padx=5, pady=5)
        
        self.mpl_button = ttk.Button(self.charts_frame, text="Show Matplotlib Chart", command=self.show_mpl_chart)
        self.mpl_button.grid(row=0, column=1, padx=5, pady=5)
        
        # Search functionality
        self.search_frame = ttk.LabelFrame(self.root, text="Search Items")
        self.search_frame.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        
        ttk.Label(self.search_frame, text="Item Name:").grid(row=0, column=0, padx=5, pady=5)
        self.search_entry = ttk.Entry(self.search_frame)
        self.search_entry.grid(row=0, column=1, padx=5, pady=5)
        
        self.search_button = ttk.Button(self.search_frame, text="Search", command=self.search_item)
        self.search_button.grid(row=0, column=2, padx=5, pady=5)
    
    def register_user(self):
        username = self.username_entry.get()
        email = self.email_entry.get()
        phone = self.phone_entry.get()
        min_profit = int(self.min_profit_entry.get())
        min_margin = float(self.min_margin_entry.get())
        register_user(username, email, phone, min_profit, min_margin)
        messagebox.showinfo("Registration", "User registered successfully!")
    
    def analyze_data(self):
        min_profit = int(self.analysis_min_profit_entry.get())
        min_margin = float(self.analysis_min_margin_entry.get())
        df = fetch_and_process_data(min_profit, min_margin)
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, df.head(10).to_string())
    
    def save_to_excel(self):
        df = fetch_and_process_data()
        filename = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if filename:
            save_data_to_excel(df, filename)
            messagebox.showinfo("Save to Excel", f"Data saved to {filename}")
    
    def show_plotly_chart(self):
        df = fetch_and_process_data()
        display_data_plotly(df)
    
    def show_mpl_chart(self):
        df = fetch_and_process_data()
        display_data(df)
    
    def search_item(self):
        item_name = self.search_entry.get()
        df = fetch_and_process_data()
        filtered_df = df[df['Item'].str.contains(item_name, case=False)]
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, filtered_df.to_string())

# Unit tests
class TestOSRSFlippingTool(unittest.TestCase):

    @patch('requests.get')
    def test_fetch_real_time_data(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'data': {
                '123': {
                    'name': 'Test Item',
                    'buy_average': 100,
                    'sell_average': 150,
                    'buy_quantity': 1000,
                    'sell_quantity': 500
                }
            }
        }
        mock_get.return_value = mock_response
        
        df = fetch_real_time_data()
        self.assertFalse(df.empty)
        self.assertEqual(df.iloc[0]['Item'], 'Test Item')
        self.assertEqual(df.iloc[0]['Buy Price'], 100)
        self.assertEqual(df.iloc[0]['Sell Price'], 150)
        self.assertEqual(df.iloc[0]['Buy Quantity'], 1000)
        self.assertEqual(df.iloc[0]['Sell Quantity'], 500)
        self.assertEqual(df.iloc[0]['Profit'], 50)

    def test_clean_data(self):
        data = {
            'Item': ['Test Item'],
            'Buy Price': [100.0],
            'Sell Price': [150.0],
            'Buy Quantity': [1000],
            'Sell Quantity': [500],
            'Profit': [50.0]
        }
        df = pd.DataFrame(data)
        clean_df = clean_data(df)
        self.assertEqual(clean_df.iloc[0]['Buy Price'], 100)
        self.assertEqual(clean_df.iloc[0]['Sell Price'], 150)
        self.assertEqual(clean_df.iloc[0]['Profit'], 50)

    def test_analyze_data(self):
        data = {
            'Item': ['Test Item'],
            'Buy Price': [100],
            'Sell Price': [150],
            'Buy Quantity': [1000],
            'Sell Quantity': [500],
            'Profit': [50]
        }
        df = pd.DataFrame(data)
        analyzed_df = analyze_data(df, min_profit=10, min_margin=10)
        self.assertFalse(analyzed_df.empty)
        self.assertEqual(analyzed_df.iloc[0]['Item'], 'Test Item')
        self.assertEqual(analyzed_df.iloc[0]['Profit'], 50)
    
    @patch('openpyxl.Workbook.save')
    def test_save_data_to_excel(self, mock_save):
        data = {
            'Item': ['Test Item'],
            'Buy Price': [100],
            'Sell Price': [150],
            'Buy Quantity': [1000],
            'Sell Quantity': [500],
            'Profit': [50]
        }
        df = pd.DataFrame(data)
        save_data_to_excel(df, 'test_flipping_opportunities.xlsx')
        mock_save.assert_called_once()

    @patch('joblib.load')
    def test_predict_prices(self, mock_load):
        data = {
            'Item': ['Test Item'],
            'Buy Price': [100],
            'Sell Price': [150],
            'Buy Quantity': [1000],
            'Sell Quantity': [500],
            'Profit': [50]
        }
        df = pd.DataFrame(data)
        model = MagicMock()
        model.predict.return_value = [155]
        mock_load.return_value = model
        
        predicted_df = predict_prices(df)
        self.assertIn('Predicted Sell Price', predicted_df.columns)
        self.assertEqual(predicted_df.iloc[0]['Predicted Sell Price'], 155)

# Run the unit tests
if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

# Run the GUI application
if __name__ == "__main__":
    root = tk.Tk()
    app = OSRSFlippingToolApp(root)
    root.mainloop()
