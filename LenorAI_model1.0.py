import requests
from bs4 import BeautifulSoup
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
import tkinter as tk
from tkinter import messagebox
from transformers import pipeline
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import datetime
import geocoder  # Import geocoder
import win32print
import win32ui
from PIL import Image, ImageWin

# Initialize the sentiment analysis pipeline
sentiment_analyzer = pipeline("sentiment-analysis", max_length=1024)

# Set up the credentials and authorize
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("C:\\Users\\cbgow\\Desktop\\lenorai-973a6d3381d2.json", scope)
client = gspread.authorize(creds)

# Attempt to open the sheet
try:
    sheet = client.open("LenorAI_Recipes_Data").sheet1  # Your Google Sheet name
    print("Sheet opened successfully!")
except Exception as e:
    print(f"Error: {e}")

def fetch_recipe(url):
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')

        title = soup.find('h1').get_text() if soup.find('h1') else "No title found"

        ingredients = []
        instructions = []

        for item in soup.find_all(['li', 'p']):
            text = item.get_text().strip()
            if any(keyword in text.lower() for keyword in ["ingredient", "cup", "tablespoon", "teaspoon", "gram"]):
                ingredients.append(text)
            elif any(keyword in text.lower() for keyword in ["step", "instruction", "cook", "bake", "prepare"]):
                instructions.append(text)

        return {'title': title, 'ingredients': ingredients, 'instructions': instructions}
    else:
        print("Failed to retrieve the recipe.")
        return None

def display_recipe(recipe):
    window = tk.Tk()
    window.title("Recipe")
    window.geometry("500x400")

    frame = tk.Frame(window)
    frame.pack(pady=10)

    recipe_text = tk.Text(frame, wrap=tk.WORD, width=60, height=15)
    recipe_text.pack(side=tk.LEFT, fill=tk.BOTH)

    scrollbar = tk.Scrollbar(frame, command=recipe_text.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    recipe_text['yscrollcommand'] = scrollbar.set

    recipe_text.insert(tk.END, f"Title: {recipe['title']}\n\n")
    recipe_text.insert(tk.END, "Ingredients:\n")
    for ingredient in recipe['ingredients']:
        recipe_text.insert(tk.END, f"- {ingredient}\n")
    recipe_text.insert(tk.END, "\nInstructions:\n")
    for idx, step in enumerate(recipe['instructions'], start=1):
        recipe_text.insert(tk.END, f"{idx}. {step}\n")

    button_frame = tk.Frame(window)
    button_frame.pack(pady=10)

    print_button = tk.Button(button_frame, text="Print", command=lambda: print_recipe(recipe))
    print_button.pack(side=tk.LEFT, padx=5)

    done_button = tk.Button(button_frame, text="Done", command=window.destroy)
    done_button.pack(side=tk.LEFT, padx=5)

    window.mainloop()

def print_recipe(recipe):
    print_content = f"Title: {recipe['title']}\n\n"
    print_content += "Ingredients:\n"
    for ingredient in recipe['ingredients']:
        print_content += f"- {ingredient}\n"
    print_content += "\nInstructions:\n"
    for idx, step in enumerate(recipe['instructions'], start=1):
        print_content += f"{idx}. {step}\n"

    # Create a temporary text file for printing
    with open("temp_recipe.txt", "w") as f:
        f.write(print_content)

    # Use win32api to send the file to the default printer
    import win32api
    import win32con

    # Get the default printer
    printer_name = win32print.GetDefaultPrinter()

    # Print the file
    win32api.ShellExecute(0, "print", "temp_recipe.txt", None, ".", 0)

    # Optionally delete the temp file after printing
    import os
    os.remove("temp_recipe.txt")


def load_data(csv_file):
    df = pd.read_csv(csv_file)
    return df

def save_new_data(title, ingredients, instructions, predicted_class, url, location):
    current_date = datetime.datetime.now().date()
    current_time = datetime.datetime.now().time().strftime("%H:%M:%S")

    new_data = {
        'Title': title,
        'Ingredients': ', '.join(ingredients),
        'Instructions': ', '.join(instructions),
        'URL': url,
        'Date': current_date,
        'Timestamp': current_time,
        'Location': location
    }

    try:
        print("Appending data to Google Sheets:", new_data)
        sheet.append_row([title, ', '.join(ingredients), ', '.join(instructions), predicted_class, url, str(current_date), current_time, location])
        print("Data saved to Google Sheets successfully!")
    except Exception as e:
        print(f"Error saving data to Google Sheets: {e}")

def fetch_updated_data():
    # Fetch all data from the Google Sheet
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def train_model(df):
    X = df['Ingredients'] + " " + df['Instructions']
    y = df['Title']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    vectorizer = CountVectorizer()
    X_train_counts = vectorizer.fit_transform(X_train)

    model = MultinomialNB()
    model.fit(X_train_counts, y_train)

    return model, vectorizer

def update_model(model, vectorizer):
    # Fetch updated data from Google Sheets
    new_data = fetch_updated_data()
    
    # Ensure there is new data to update the model
    if not new_data.empty:
        X_new = new_data['Ingredients'] + " " + new_data['Instructions']
        y_new = new_data['Predicted Class']

        X_new_counts = vectorizer.transform(X_new)
        model.partial_fit(X_new_counts, y_new, classes=model.classes_)

def scrape_and_save():
    url = url_entry.get()
    recipe = fetch_recipe(url)
    
    if recipe:
        display_recipe(recipe)

        combined_text = ' '.join(recipe['ingredients']) + " " + ' '.join(recipe['instructions'])
        
        # Ensure the length is within the limit for sentiment analysis
        if len(combined_text) > 1024:
            combined_text = combined_text[:1024]  # Truncate to first 1024 characters
        
        predicted_class = sentiment_analyzer(combined_text)[0]['label']
        
        # Get the device's location
        g = geocoder.ip('me')
        location = g.city if g.city else "Location not found"
        
        save_new_data(recipe['title'], recipe['ingredients'], recipe['instructions'], predicted_class, url, location)
        
        update_model(model, vectorizer)
        
        messagebox.showinfo("Success", "Recipe saved successfully!")
    else:
        messagebox.showerror("Whoopsy", "¯\\_(0-0)_/¯")

def create_gui():
    global url_entry
    
    window = tk.Tk()
    window.title("Recipe Scraper")

    tk.Label(window, text="Enter Recipe URL:").pack(pady=10)

    url_entry = tk.Entry(window, width=50)
    url_entry.pack(pady=10)

    scrape_button = tk.Button(window, text="Generate", command=scrape_and_save)
    scrape_button.pack(pady=20)

    window.mainloop()

if __name__ == "__main__":
    csv_file = 'Recipe Reader - Sheet1.csv'
    df = load_data(csv_file)

    model, vectorizer = train_model(df)

    create_gui()
