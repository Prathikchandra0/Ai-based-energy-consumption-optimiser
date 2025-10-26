# AI-Based Energy Consumption Optimizer — Streamlit Dashboard

This small Streamlit app analyzes historical energy data (CSV) and recommends the cheapest hours to schedule a given number of electricity units (kWh). It presents an animated bar chart that shows expected cost per hour and a clean recommendation table.

How it works
- The app auto-detects a CSV file in the project root.
- It expects a datetime-like column and a numeric consumption column (names like `datetime`, `timestamp`, `usage`, `consumption`, `units` are detected automatically).
- If the dataset contains a `cost`/`price`/`bill` column, the app computes true price-per-unit by hour.
- If there's no cost column, the app uses historical hourly consumption as a proxy: hours with lower historical consumption are treated as cheaper.

Files added
- `app.py` — Streamlit dashboard (UI, plotting, recommendations).
- `utils.py` — helpers to detect/load the dataset and compute hourly price/proxy.
- `requirements.txt` — Python packages used.

Usage
1. Put your dataset CSV into the project root (the same folder as `app.py`).
2. Install dependencies into your environment. Example (PowerShell):

```powershell
python -m pip install -r "c:\Users\vuppa\OneDrive\Desktop\energy_consumption 2\requirements.txt"
```

3. Run the Streamlit app (PowerShell):

```powershell
cd "c:\Users\vuppa\OneDrive\Desktop\energy_consumption 2"
streamlit run app.py
```

Notes & assumptions
- If your CSV has non-standard column names, rename or provide a simple header that includes a datetime and a numeric consumption column.
- The app uses a simple data-driven approach rather than a complex black-box model. This keeps recommendations explainable — shifting usage into historically low-demand (or low-cost) hours.

Next improvements (optional)
- Add a small training script or persistent model if you want predictive time-series forecasts.
- Support user-uploaded CSVs in the UI (currently the app auto-loads the CSV in the project root).
- Add a richer Lottie animation loaded from an online URL or local asset for a more polished header.

If you'd like, give me the actual CSV filename or attach it here and I can adapt the app to the exact column names and run a quick local validation script for you.
