# Travel Intelligence Pipeline

End-to-end data pipeline to rank travel destinations using weather indicators and accommodation-related signals.

---

## Overview
This project implements a data pipeline that aggregates weather data and accommodation-related signals to compute and rank destination attractiveness.

It is designed as a prototype for travel analytics use cases such as content recommendation, destination ranking, or marketing prioritization.

---

## Key Capabilities
- Collect and integrate heterogeneous data sources (weather APIs, geolocation, web data)
- Compute a destination-level scoring based on multiple signals
- Rank destinations according to computed attractiveness
- Generate visual outputs for exploration and comparison

---

## Data Sources

### Cities
35 major French destinations  
GPS coordinates retrieved via the Nominatim API.

### Weather (API)
OpenWeather One Call API  
- Temperature  
- Expected rainfall  
- Custom “nice weather” score  

### Accommodation Data (Web Extraction)
- Hotel name  
- GPS coordinates  
- Review score  
- Description + address  

Data is collected from publicly available web pages for prototyping purposes.

---

## Pipeline Architecture

1. Data ingestion (geolocation, weather API, web data extraction)  
2. Data cleaning and feature engineering  
3. Aggregation at destination level  
4. Storage in AWS S3 (data lake)  
5. Loading into PostgreSQL (analytical layer)  
6. Visualization and ranking outputs  

---

## Tech Stack
- Python (pandas, scrapy, requests)  
- APIs: Nominatim, OpenWeather  
- AWS S3 (data lake)  
- AWS RDS PostgreSQL (analytical storage)  
- Plotly  

---

## Project Structure
- Geolocation ingestion notebook  
- Weather data processing and scoring  
- Web scraping module (accommodation data)  
- Data merging and cleaning  
- SQL loading scripts  
- Visualization notebooks  

---

## Example Output
- Ranked list of destinations based on computed score  
- Map visualization highlighting top destinations  
- Dataset ready for downstream usage (BI / API / dashboard)  

---

## Limitations
- Prototype project (non-production data reliability)  
- Limited coverage of accommodation sources  
- Heuristic scoring approach (non machine learning-based)  

---

## Context
This project is a portfolio prototype designed to illustrate how data pipelines can support travel-related decision-making through aggregation, scoring, and visualization.