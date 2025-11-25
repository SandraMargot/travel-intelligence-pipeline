# Kayak - A data-driven holiday destination recommender
A data science project for Jedha

## Overview
This project builds a simple, data-powered engine to help travellers choose the best French destinations based on real weather forecasts and hotel quality.

## What it does
- Identifies the top French destinations for the next 7 days  
- Selects the best hotels in each area  
- Generates two interactive Plotly maps:  
  - Top-5 destinations  
  - Top-20 hotels  
All insights come from real APIs and real scraping.
---
## Data Used
### Cities
35 major French destinations  
GPS from the Nominatim API.
### Weather (API)
OpenWeather One Call API  
- Temperature  
- Expected rainfall  
- Custom “nice weather” score  
### Hotels (Scraping)
Booking.com  
- Hotel name  
- GPS coordinates  
- Review score  
- Description + address  
---
## Pipeline (Simplified)
1. GPS → Weather → Hotels  
2. Clean & merge into final enriched CSV  
3. Store in AWS S3 (Data Lake)  
4. Load into AWS RDS PostgreSQL (Data Warehouse)  
5. Build maps with Plotly
---
## Tech Stack
- Python (pandas, scrapy, requests)  
- APIs: Nominatim, OpenWeather  
- AWS S3 : datalake
- RDS : datawarehouse in PostgreSQL (SQL : staging, dim_site, fact_hotel)
- Plotly  
---
## 📁 Key Files
- city coordinates : 01-Kayak-API-GPS.ipynb
- weather + scores : Project2-Kayak-API-Weather.ipynb
- hotel scraper : scraping_booking_hotels.py  
- creation final dataset : Kayak-merge_and_clean.ipynb
- AWS S3 bucket : Snapshot AWS - S3.png
- AWS RDS db : Snapshot AWS - RDS.png
- S3 → RDS loading : queries.sql
- maps : Hotels_map.ipynb
---
## Secrets
1. Copy .env.example to .env
2. Edit .env by filling in your own values
3. Open the project folder in VS Code
4. Open any notebook and run it