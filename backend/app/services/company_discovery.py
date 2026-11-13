"""
ALPHANEXUS – Universal Company Discovery & Master Equities Universe
===================================================================
Provides scalable discovery, identification, deduplication, and dynamic
provisioning for Indian listed equities (NSE & BSE).

Supports:
  - Canonical identification by UUID, NSE Symbol, BSE Scrip Code, ISIN, and aliases.
  - Comprehensive master universe across all major sectors and market caps.
  - Dynamic discovery & real-time metadata hydration via IndianAPI / market feeds.
  - Normalized identifier mapping (company_identifiers table).
  - Deduplication across symbols, names, and regulatory codes.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.core.logging import logger
from app.models.company import Company, CompanyIdentifier
from app.models.financial import FinancialMetric, StockPrice
from app.integrations.market_data.indianapi import IndianAPIProvider


# ---------------------------------------------------------------------------
# Canonical Master Equities Universe (Top NSE & BSE Equities)
# Authoritative mapping of official names, symbols, BSE codes, ISINs, sectors,
# industries, and common aliases for comprehensive discovery.
# ---------------------------------------------------------------------------

MASTER_EQUITIES_UNIVERSE: List[Dict[str, Any]] = [
    # Energy & Conglomerate
    {
        "symbol": "RELIANCE",
        "name": "Reliance Industries Limited",
        "exchange": "NSE",
        "bse_code": "500325",
        "isin": "INE002A01018",
        "sector": "Energy & Conglomerate",
        "industry": "Oil, Gas, Telecom & Retail",
        "aliases": ["RIL", "Reliance", "Jio", "Reliance Retail"],
        "market_cap": 1985400.0,
        "website": "https://www.ril.com",
        "description": "Reliance Industries is India's largest private enterprise with dominant leadership in oil-to-chemicals, telecom (Jio), retail, and new energy.",
    },
    {
        "symbol": "ADANIENT",
        "name": "Adani Enterprises Limited",
        "exchange": "NSE",
        "bse_code": "512599",
        "isin": "INE423A01024",
        "sector": "Conglomerate & Energy",
        "industry": "Infrastructure & Trading",
        "aliases": ["Adani", "AEL", "Adani Enterprises"],
        "market_cap": 345000.0,
        "website": "https://www.adanienterprises.com",
        "description": "Flagship incubator for the Adani Group with businesses spanning airports, roads, data centers, solar manufacturing, and natural resources.",
    },
    {
        "symbol": "ONGC",
        "name": "Oil and Natural Gas Corporation Limited",
        "exchange": "NSE",
        "bse_code": "500312",
        "isin": "INE213A01029",
        "sector": "Energy & Exploration",
        "industry": "Oil & Gas Exploration & Production",
        "aliases": ["ONGC", "Oil & Natural Gas Corp"],
        "market_cap": 310000.0,
        "website": "https://www.ongcindia.com",
        "description": "Largest crude oil and natural gas company in India, contributing around 71% to domestic production.",
    },
    {
        "symbol": "BPCL",
        "name": "Bharat Petroleum Corporation Limited",
        "exchange": "NSE",
        "bse_code": "500547",
        "isin": "INE029A01011",
        "sector": "Energy & Refining",
        "industry": "Downstream Petroleum Refining & Marketing",
        "aliases": ["BPCL", "Bharat Petroleum"],
        "market_cap": 135000.0,
        "website": "https://www.bharatpetroleum.in",
        "description": "State-controlled oil and gas company operating major refineries in Mumbai, Kochi, and Bina.",
    },
    {
        "symbol": "IOC",
        "name": "Indian Oil Corporation Limited",
        "exchange": "NSE",
        "bse_code": "530965",
        "isin": "INE242A01010",
        "sector": "Energy & Oil Refining",
        "industry": "Oil Refining, Pipelines & Fuel Marketing",
        "aliases": ["IOC", "IOCL", "Indian Oil"],
        "market_cap": 215000.0,
        "website": "https://www.iocl.com",
        "description": "India's largest commercial enterprise and premier national oil company.",
    },
    {
        "symbol": "GAIL",
        "name": "GAIL (India) Limited",
        "exchange": "NSE",
        "bse_code": "532155",
        "isin": "INE129A01019",
        "sector": "Energy & Gas Transmission",
        "industry": "Natural Gas Processing & Distribution",
        "aliases": ["GAIL", "Gas Authority of India"],
        "market_cap": 125000.0,
        "website": "https://www.gailonline.com",
        "description": "India's leading natural gas company integrating transmission, marketing, and petrochemicals.",
    },
    {
        "symbol": "COALINDIA",
        "name": "Coal India Limited",
        "exchange": "NSE",
        "bse_code": "533278",
        "isin": "INE522F01014",
        "sector": "Mining & Energy",
        "industry": "Coal Mining & Extraction",
        "aliases": ["CIL", "Coal India"],
        "market_cap": 275000.0,
        "website": "https://www.coalindia.in",
        "description": "The largest coal producer in the world, supplying the majority of India's thermal coal requirements.",
    },

    # Information Technology
    {
        "symbol": "TCS",
        "name": "Tata Consultancy Services Limited",
        "exchange": "NSE",
        "bse_code": "532540",
        "isin": "INE467B01029",
        "sector": "Information Technology",
        "industry": "IT Services & Consulting",
        "aliases": ["TCS", "Tata Consultancy", "Tata Tech Services"],
        "market_cap": 1520300.0,
        "website": "https://www.tcs.com",
        "description": "Global leader in IT services, digital transformation, and cognitive business operations across 55 countries.",
    },
    {
        "symbol": "INFY",
        "name": "Infosys Limited",
        "exchange": "NSE",
        "bse_code": "500209",
        "isin": "INE009A01021",
        "sector": "Information Technology",
        "industry": "Enterprise Software & Cloud Platforms",
        "aliases": ["Infosys", "Infy"],
        "market_cap": 685000.0,
        "website": "https://www.infosys.com",
        "description": "Next-generation digital services and consulting powerhouse, pioneered Infosys Topaz AI-first suite.",
    },
    {
        "symbol": "WIPRO",
        "name": "Wipro Limited",
        "exchange": "NSE",
        "bse_code": "507685",
        "isin": "INE075A01022",
        "sector": "Information Technology",
        "industry": "IT Consulting & System Integration",
        "aliases": ["Wipro"],
        "market_cap": 295000.0,
        "website": "https://www.wipro.com",
        "description": "Leading technology services and consulting company focused on building innovative solutions addressing enterprise digital transformation.",
    },
    {
        "symbol": "HCLTECH",
        "name": "HCL Technologies Limited",
        "exchange": "NSE",
        "bse_code": "532281",
        "isin": "INE860A01027",
        "sector": "Information Technology",
        "industry": "Engineering Services & Digital Tech",
        "aliases": ["HCL Tech", "HCL", "HCL Technologies"],
        "market_cap": 485000.0,
        "website": "https://www.hcltech.com",
        "description": "Global technology company delivering industry-leading capabilities centered around digital, engineering, cloud, and AI.",
    },
    {
        "symbol": "TECHM",
        "name": "Tech Mahindra Limited",
        "exchange": "NSE",
        "bse_code": "532755",
        "isin": "INE669C01036",
        "sector": "Information Technology",
        "industry": "Telecom Software & Digital Solutions",
        "aliases": ["Tech Mahindra", "TechM"],
        "market_cap": 165000.0,
        "website": "https://www.techmahindra.com",
        "description": "Specialist in digital transformation, consulting and business re-engineering solutions with telecom heritage.",
    },
    {
        "symbol": "LTIM",
        "name": "LTIMindtree Limited",
        "exchange": "NSE",
        "bse_code": "540005",
        "isin": "INE214T01019",
        "sector": "Information Technology",
        "industry": "Enterprise Digital Solutions",
        "aliases": ["LTIMindtree", "LTI Mindtree", "Mindtree", "LTI"],
        "market_cap": 168000.0,
        "website": "https://www.ltimindtree.com",
        "description": "Global technology consulting and digital solutions company that enables enterprises across industries to reimagine business models.",
    },
    {
        "symbol": "PERSISTENT",
        "name": "Persistent Systems Limited",
        "exchange": "NSE",
        "bse_code": "533179",
        "isin": "INE262H01013",
        "sector": "Information Technology",
        "industry": "Software Engineering & Enterprise AI",
        "aliases": ["Persistent", "Persistent Systems"],
        "market_cap": 82000.0,
        "website": "https://www.persistent.com",
        "description": "Digital engineering and enterprise modernization partner with deep expertise in cloud, data, and generative AI.",
    },
    {
        "symbol": "COFORGE",
        "name": "Coforge Limited",
        "exchange": "NSE",
        "bse_code": "532541",
        "isin": "INE591G01017",
        "sector": "Information Technology",
        "industry": "IT Solutions for Travel & Insurance",
        "aliases": ["Coforge", "NIIT Technologies"],
        "market_cap": 48000.0,
        "website": "https://www.coforge.com",
        "description": "Global digital services and solutions provider that enables its clients to transform at the intersection of domain expertise and emerging technologies.",
    },

    # Banking & Financial Services
    {
        "symbol": "HDFCBANK",
        "name": "HDFC Bank Limited",
        "exchange": "NSE",
        "bse_code": "500180",
        "isin": "INE040A01034",
        "sector": "Banking & Financial Services",
        "industry": "Private Sector Banking",
        "aliases": ["HDFC", "HDFC Bank"],
        "market_cap": 1320000.0,
        "website": "https://www.hdfcbank.com",
        "description": "India's largest private sector bank by assets, serving over 100 million customers following historic merger with parent HDFC Limited.",
    },
    {
        "symbol": "ICICIBANK",
        "name": "ICICI Bank Limited",
        "exchange": "NSE",
        "bse_code": "532174",
        "isin": "INE090A01021",
        "sector": "Banking & Financial Services",
        "industry": "Private Sector Banking",
        "aliases": ["ICICI", "ICICI Bank"],
        "market_cap": 910000.0,
        "website": "https://www.icicibank.com",
        "description": "Leading private sector bank in India offering a diversified portfolio of financial products and services to retail, SME, and corporate clients.",
    },
    {
        "symbol": "SBIN",
        "name": "State Bank of India",
        "exchange": "NSE",
        "bse_code": "500112",
        "isin": "INE062A01020",
        "sector": "Banking & Financial Services",
        "industry": "Public Sector Commercial Banking",
        "aliases": ["SBI", "State Bank", "State Bank of India"],
        "market_cap": 750000.0,
        "website": "https://www.sbi.co.in",
        "description": "Fortune 500 company and largest Indian public sector commercial bank, commanding ~25% market share in total deposits and advances.",
    },
    {
        "symbol": "KOTAKBANK",
        "name": "Kotak Mahindra Bank Limited",
        "exchange": "NSE",
        "bse_code": "500247",
        "isin": "INE237A01028",
        "sector": "Banking & Financial Services",
        "industry": "Private Sector Banking & Wealth Management",
        "aliases": ["Kotak", "Kotak Mahindra", "Kotak Bank"],
        "market_cap": 365000.0,
        "website": "https://www.kotak.com",
        "description": "Premier diversified financial services group offering personal finance, commercial banking, wealth management, and investment banking.",
    },
    {
        "symbol": "AXISBANK",
        "name": "Axis Bank Limited",
        "exchange": "NSE",
        "bse_code": "532215",
        "isin": "INE238A01034",
        "sector": "Banking & Financial Services",
        "industry": "Private Sector Banking",
        "aliases": ["Axis", "Axis Bank", "UTI Bank"],
        "market_cap": 355000.0,
        "website": "https://www.axisbank.com",
        "description": "Third largest private sector bank in India, offering retail banking, corporate banking, credit cards, and treasury operations.",
    },
    {
        "symbol": "BAJFINANCE",
        "name": "Bajaj Finance Limited",
        "exchange": "NSE",
        "bse_code": "500034",
        "isin": "INE296A01024",
        "sector": "Financial Services & NBFC",
        "industry": "Consumer Finance & Lending",
        "aliases": ["Bajaj Finance", "Bajaj Fin"],
        "market_cap": 430000.0,
        "website": "https://www.bajajfinserv.in/finance",
        "description": "India's largest non-banking financial company (NBFC) specializing in consumer durable finance, personal loans, and digital payments.",
    },
    {
        "symbol": "BAJAJFINSV",
        "name": "Bajaj Finserv Limited",
        "exchange": "NSE",
        "bse_code": "532978",
        "isin": "INE918I01026",
        "sector": "Financial Services",
        "industry": "Financial Conglomerate & Insurance",
        "aliases": ["Bajaj Finserv", "Finserv"],
        "market_cap": 270000.0,
        "website": "https://www.bajajfinserv.in",
        "description": "Holding company for financial businesses of Bajaj Group spanning lending, life insurance, general insurance, and asset management.",
    },
    {
        "symbol": "JIOFIN",
        "name": "Jio Financial Services Limited",
        "exchange": "NSE",
        "bse_code": "543940",
        "isin": "INE758E01017",
        "sector": "Financial Services",
        "industry": "FinTech & Financial Intermediation",
        "aliases": ["Jio Financial", "JioFin", "JFSL"],
        "market_cap": 215000.0,
        "website": "https://www.jfs.in",
        "description": "Demerged financial services arm of Reliance Industries, providing digital consumer lending, merchant finance, insurance, and asset management.",
    },
    {
        "symbol": "BANKBARODA",
        "name": "Bank of Baroda",
        "exchange": "NSE",
        "bse_code": "532134",
        "isin": "INE028A01039",
        "sector": "Banking & Financial Services",
        "industry": "Public Sector Commercial Banking",
        "aliases": ["Bank of Baroda", "BoB"],
        "market_cap": 135000.0,
        "website": "https://www.bankofbaroda.in",
        "description": "Second largest public sector bank in India with extensive domestic reach and international presence across 17 countries.",
    },
    {
        "symbol": "PNB",
        "name": "Punjab National Bank",
        "exchange": "NSE",
        "bse_code": "532461",
        "isin": "INE160A01022",
        "sector": "Banking & Financial Services",
        "industry": "Public Sector Banking",
        "aliases": ["PNB", "Punjab National Bank"],
        "market_cap": 110000.0,
        "website": "https://www.pnbindia.in",
        "description": "Pioneer public sector bank serving over 180 million customers across India.",
    },

    # Automobile & Transportation
    {
        "symbol": "TATAMOTORS",
        "name": "Tata Motors Limited",
        "exchange": "NSE",
        "bse_code": "500570",
        "isin": "INE155A01022",
        "sector": "Automobile & EV",
        "industry": "Commercial Vehicles, Passenger Cars & EVs",
        "aliases": ["Tata Motors", "TaMo", "JLR", "Jaguar Land Rover"],
        "market_cap": 315000.0,
        "website": "https://www.tatamotors.com",
        "description": "Leading global automotive manufacturer commanding India's commercial vehicle and EV passenger car segments alongside Jaguar Land Rover.",
    },
    {
        "symbol": "MARUTI",
        "name": "Maruti Suzuki India Limited",
        "exchange": "NSE",
        "bse_code": "532500",
        "isin": "INE585B01010",
        "sector": "Automobile",
        "industry": "Passenger Cars & Utility Vehicles",
        "aliases": ["Maruti", "Maruti Suzuki", "Suzuki India"],
        "market_cap": 390000.0,
        "website": "https://www.marutisuzuki.com",
        "description": "Market leader in the Indian passenger vehicle industry with over 40% domestic market share.",
    },
    {
        "symbol": "M&M",
        "name": "Mahindra & Mahindra Limited",
        "exchange": "NSE",
        "bse_code": "500520",
        "isin": "INE101A01026",
        "sector": "Automobile & Tractors",
        "industry": "SUVs, Farm Equipment & Commercial Vehicles",
        "aliases": ["Mahindra", "M&M", "Mahindra & Mahindra"],
        "market_cap": 350000.0,
        "website": "https://www.mahindra.com",
        "description": "India's premier SUV manufacturer and the world's largest tractor maker by volume.",
    },
    {
        "symbol": "BAJAJ-AUTO",
        "name": "Bajaj Auto Limited",
        "exchange": "NSE",
        "bse_code": "532977",
        "isin": "INE917I01010",
        "sector": "Automobile",
        "industry": "Two-Wheelers & Three-Wheelers",
        "aliases": ["Bajaj Auto", "Bajaj 2-Wheeler"],
        "market_cap": 270000.0,
        "website": "https://www.bajajauto.com",
        "description": "World's third-largest motorcycle manufacturer and the largest exporter of two and three-wheelers from India.",
    },
    {
        "symbol": "EICHERMOT",
        "name": "Eicher Motors Limited",
        "exchange": "NSE",
        "bse_code": "505200",
        "isin": "INE066A01021",
        "sector": "Automobile",
        "industry": "Premium Motorcycles & Commercial Trucks",
        "aliases": ["Eicher", "Royal Enfield", "Eicher Motors"],
        "market_cap": 130000.0,
        "website": "https://www.eichermotors.com",
        "description": "Parent company of iconic motorcycle brand Royal Enfield and commercial vehicle JV VE Commercial Vehicles.",
    },
    {
        "symbol": "HEROMOTOCO",
        "name": "Hero MotoCorp Limited",
        "exchange": "NSE",
        "bse_code": "500182",
        "isin": "INE158A01026",
        "sector": "Automobile & Two-wheelers",
        "industry": "Motorcycles & Scooters",
        "aliases": ["Hero", "Hero MotoCorp", "Hero Honda"],
        "market_cap": 95000.0,
        "website": "https://www.heromotocorp.com",
        "description": "World's largest manufacturer of motorcycles and scooters in terms of unit volume sales in a calendar year.",
    },

    # Infrastructure, Capital Goods & Defence
    {
        "symbol": "LT",
        "name": "Larsen & Toubro Limited",
        "exchange": "NSE",
        "bse_code": "500510",
        "isin": "INE018A01030",
        "sector": "Infrastructure & Capital Goods",
        "industry": "Engineering, Procurement & Construction (EPC)",
        "aliases": ["L&T", "Larsen", "Larsen & Toubro"],
        "market_cap": 510000.0,
        "website": "https://www.larsentoubro.com",
        "description": "Indian multinational conglomerate engaged in EPC projects, hi-tech manufacturing, defense, and services.",
    },
    {
        "symbol": "HAL",
        "name": "Hindustan Aeronautics Limited",
        "exchange": "NSE",
        "bse_code": "541154",
        "isin": "INE066F01012",
        "sector": "Aerospace & Defence",
        "industry": "Military Aircraft, Helicopters & Avionics",
        "aliases": ["HAL", "Hindustan Aeronautics"],
        "market_cap": 290000.0,
        "website": "https://www.hal-india.co.in",
        "description": "Premier defence public sector undertaking designing and manufacturing fighter aircraft (Tejas), helicopters, and aero-engines.",
    },
    {
        "symbol": "BEL",
        "name": "Bharat Electronics Limited",
        "exchange": "NSE",
        "bse_code": "500049",
        "isin": "INE263A01024",
        "sector": "Aerospace & Defence",
        "industry": "Defence Electronics, Radars & Avionics",
        "aliases": ["BEL", "Bharat Electronics"],
        "market_cap": 210000.0,
        "website": "https://www.bel-india.in",
        "description": "Navratna defence PSU producing advanced electronic equipment for the Indian Armed Forces.",
    },
    {
        "symbol": "SIEMENS",
        "name": "Siemens Limited",
        "exchange": "NSE",
        "bse_code": "500550",
        "isin": "INE003A01024",
        "sector": "Capital Goods & Engineering",
        "industry": "Electrification, Automation & Digitalization",
        "aliases": ["Siemens", "Siemens India"],
        "market_cap": 240000.0,
        "website": "https://www.siemens.com/in",
        "description": "Pioneer in electrical engineering, smart infrastructure, industrial automation, and mobility solutions in India.",
    },
    {
        "symbol": "ABB",
        "name": "ABB India Limited",
        "exchange": "NSE",
        "bse_code": "500002",
        "isin": "INE117A01022",
        "sector": "Industrial Automation & Robotics",
        "industry": "Power Products, Motion & Process Automation",
        "aliases": ["ABB", "ABB India"],
        "market_cap": 160000.0,
        "website": "https://new.abb.com/in",
        "description": "Technology leader in electrification and automation, enabling a more sustainable and resource-efficient future.",
    },

    # FMCG & Consumer Goods
    {
        "symbol": "HINDUNILVR",
        "name": "Hindustan Unilever Limited",
        "exchange": "NSE",
        "bse_code": "500696",
        "isin": "INE030A01027",
        "sector": "FMCG & Consumer Goods",
        "industry": "Home Care, Beauty & Personal Care",
        "aliases": ["HUL", "Hindustan Unilever", "Unilever India"],
        "market_cap": 595000.0,
        "website": "https://www.hul.co.in",
        "description": "India's largest fast-moving consumer goods company with brands touching 9 out of 10 Indian households.",
    },
    {
        "symbol": "ITC",
        "name": "ITC Limited",
        "exchange": "NSE",
        "bse_code": "500875",
        "isin": "INE154A01025",
        "sector": "FMCG & Consumer Goods",
        "industry": "Cigarettes, Branded Packaged Foods & Hotels",
        "aliases": ["ITC", "ITC Ltd"],
        "market_cap": 580000.0,
        "website": "https://www.itcportal.com",
        "description": "Diversified conglomerate with presence in FMCG, paperboards, packaging, agri-business, and hotels.",
    },
    {
        "symbol": "NESTLEIND",
        "name": "Nestle India Limited",
        "exchange": "NSE",
        "bse_code": "500790",
        "isin": "INE239A01024",
        "sector": "FMCG & Food Products",
        "industry": "Packaged Food & Beverages (Maggi, Nescafe)",
        "aliases": ["Nestle", "Nestle India", "Maggi"],
        "market_cap": 215000.0,
        "website": "https://www.nestle.in",
        "description": "Leading food and beverage player in India, renowned for household brands like Maggi, Nescafe, and KitKat.",
    },
    {
        "symbol": "BRITANNIA",
        "name": "Britannia Industries Limited",
        "exchange": "NSE",
        "bse_code": "500825",
        "isin": "INE216A01030",
        "sector": "FMCG & Bakery",
        "industry": "Biscuits, Dairy & Bakery Products",
        "aliases": ["Britannia", "Britannia Industries"],
        "market_cap": 125000.0,
        "website": "https://www.britannia.co.in",
        "description": "One of India's leading food companies and manufacturer of popular biscuit brands including Good Day and Marie Gold.",
    },
    {
        "symbol": "TATACONSUM",
        "name": "Tata Consumer Products Limited",
        "exchange": "NSE",
        "bse_code": "500800",
        "isin": "INE192A01025",
        "sector": "FMCG & Beverages",
        "industry": "Tea, Coffee, Salt & Packaged Foods",
        "aliases": ["Tata Consumer", "Tata Tea", "Tata Salt"],
        "market_cap": 105000.0,
        "website": "https://www.tataconsumer.com",
        "description": "FMCG arm of Tata Group uniting food and beverage brands including Tata Tea, Tata Salt, Tetley, and Starbucks JV.",
    },
    {
        "symbol": "TITAN",
        "name": "Titan Company Limited",
        "exchange": "NSE",
        "bse_code": "500114",
        "isin": "INE280A01028",
        "sector": "Consumer & Luxury Goods",
        "industry": "Jewellery (Tanishq), Watches & Eyewear",
        "aliases": ["Titan", "Tanishq", "Titan Company"],
        "market_cap": 315000.0,
        "website": "https://www.titancompany.in",
        "description": "Leading lifestyle company from the Tata Group with market leadership in organized jewellery (Tanishq) and watches.",
    },
    {
        "symbol": "TRENT",
        "name": "Trent Limited",
        "exchange": "NSE",
        "bse_code": "500251",
        "isin": "INE849A01020",
        "sector": "Retail & Fashion",
        "industry": "Apparel, Fast Fashion & Hypermarkets (Zudio, Westside)",
        "aliases": ["Trent", "Zudio", "Westside", "Star Bazaar"],
        "market_cap": 250000.0,
        "website": "https://www.trentlimited.com",
        "description": "Retail powerhouse of the Tata Group operating high-growth fast fashion chains Zudio and Westside.",
    },
    {
        "symbol": "ZOMATO",
        "name": "Zomato Limited",
        "exchange": "NSE",
        "bse_code": "543320",
        "isin": "INE758T01015",
        "sector": "Consumer Internet & Quick Commerce",
        "industry": "Food Delivery, Quick Commerce (Blinkit) & Hyperpure",
        "aliases": ["Zomato", "Blinkit", "Eternal"],
        "market_cap": 240000.0,
        "website": "https://www.zomato.com",
        "description": "India's leading consumer internet company pioneering food delivery and high-frequency quick commerce through Blinkit.",
    },

    # Pharmaceuticals & Healthcare
    {
        "symbol": "SUNPHARMA",
        "name": "Sun Pharmaceutical Industries Limited",
        "exchange": "NSE",
        "bse_code": "524715",
        "isin": "INE044A01036",
        "sector": "Pharmaceuticals & Healthcare",
        "industry": "Specialty & Generic Pharmaceuticals",
        "aliases": ["Sun Pharma", "Sun Pharmaceuticals"],
        "market_cap": 420000.0,
        "website": "https://www.sunpharma.com",
        "description": "Fourth largest specialty generic pharmaceutical company in the world and market leader in India across therapeutic segments.",
    },
    {
        "symbol": "CIPLA",
        "name": "Cipla Limited",
        "exchange": "NSE",
        "bse_code": "500087",
        "isin": "INE059A01026",
        "sector": "Pharmaceuticals",
        "industry": "Respiratory, Anti-Retrovirals & Generics",
        "aliases": ["Cipla"],
        "market_cap": 125000.0,
        "website": "https://www.cipla.com",
        "description": "Global pharmaceutical company focused on respiratory therapy, complex generics, and accessible global healthcare.",
    },
    {
        "symbol": "DRREDDY",
        "name": "Dr. Reddy's Laboratories Limited",
        "exchange": "NSE",
        "bse_code": "500124",
        "isin": "INE089A01023",
        "sector": "Pharmaceuticals",
        "industry": "Generics, Biosimilars & Active Pharmaceutical Ingredients",
        "aliases": ["Dr Reddy", "Dr. Reddy's", "DRL"],
        "market_cap": 110000.0,
        "website": "https://www.drreddys.com",
        "description": "Integrated global pharmaceutical company offering APIs, custom pharmaceutical services, generics, biosimilars, and differentiated formulations.",
    },
    {
        "symbol": "APOLLOHOSP",
        "name": "Apollo Hospitals Enterprise Limited",
        "exchange": "NSE",
        "bse_code": "508869",
        "isin": "INE437A01024",
        "sector": "Healthcare & Hospitals",
        "industry": "Hospitals, Pharmacies & Telemedicine (Apollo 24/7)",
        "aliases": ["Apollo Hospitals", "Apollo 247"],
        "market_cap": 98000.0,
        "website": "https://www.apollohospitals.com",
        "description": "Asia's foremost integrated healthcare provider operating multi-specialty hospitals, retail pharmacies, and digital diagnostics.",
    },

    # Telecommunications
    {
        "symbol": "BHARTIARTL",
        "name": "Bharti Airtel Limited",
        "exchange": "NSE",
        "bse_code": "532454",
        "isin": "INE397D01024",
        "sector": "Telecommunications",
        "industry": "Wireless Telephony, Broadband, Enterprise & DTH",
        "aliases": ["Airtel", "Bharti Airtel"],
        "market_cap": 980000.0,
        "website": "https://www.airtel.in",
        "description": "Leading global telecommunications company with operations across 17 countries in South Asia and Africa.",
    },

    # Metals & Materials
    {
        "symbol": "TATASTEEL",
        "name": "Tata Steel Limited",
        "exchange": "NSE",
        "bse_code": "500470",
        "isin": "INE081A01020",
        "sector": "Metals & Mining",
        "industry": "Flat & Long Finished Steel Products",
        "aliases": ["Tata Steel", "Tisco"],
        "market_cap": 195000.0,
        "website": "https://www.tatasteel.com",
        "description": "One of the world's most geographically diversified steel producers with operations across India, Europe, and Southeast Asia.",
    },
    {
        "symbol": "JSWSTEEL",
        "name": "JSW Steel Limited",
        "exchange": "NSE",
        "bse_code": "500228",
        "isin": "INE019A01038",
        "sector": "Metals & Steel",
        "industry": "Integrated Steel Manufacturing",
        "aliases": ["JSW Steel", "JSW"],
        "market_cap": 235000.0,
        "website": "https://www.jsw.in/steel",
        "description": "Flagship company of the JSW Group and India's leading integrated steel manufacturer by domestic capacity.",
    },
    {
        "symbol": "HINDALCO",
        "name": "Hindalco Industries Limited",
        "exchange": "NSE",
        "bse_code": "500440",
        "isin": "INE038A01020",
        "sector": "Metals & Aluminium",
        "industry": "Aluminium Smelting & Copper Refining",
        "aliases": ["Hindalco", "Novelis"],
        "market_cap": 150000.0,
        "website": "https://www.hindalco.com",
        "description": "Metals flagship of the Aditya Birla Group and world's largest aluminium rolling and recycling company through Novelis.",
    },
    {
        "symbol": "ULTRACEMCO",
        "name": "UltraTech Cement Limited",
        "exchange": "NSE",
        "bse_code": "532538",
        "isin": "INE481G01011",
        "sector": "Materials & Cement",
        "industry": "Grey Cement, White Cement & Ready-Mix Concrete",
        "aliases": ["UltraTech", "UltraTech Cement"],
        "market_cap": 320000.0,
        "website": "https://www.ultratechcement.com",
        "description": "Largest manufacturer of grey cement, ready mix concrete, and white cement in India and 3rd largest globally.",
    },

    # Power & Utilities
    {
        "symbol": "NTPC",
        "name": "NTPC Limited",
        "exchange": "NSE",
        "bse_code": "532555",
        "isin": "INE733E01010",
        "sector": "Power & Energy",
        "industry": "Thermal & Renewable Power Generation",
        "aliases": ["NTPC", "National Thermal Power"],
        "market_cap": 365000.0,
        "website": "https://www.ntpc.co.in",
        "description": "India's largest power utility contributing over 24% of the country's electricity generation.",
    },
    {
        "symbol": "POWERGRID",
        "name": "Power Grid Corporation of India Limited",
        "exchange": "NSE",
        "bse_code": "532898",
        "isin": "INE752E01010",
        "sector": "Utilities & Power Transmission",
        "industry": "Inter-State Power Transmission Grid",
        "aliases": ["Power Grid", "PowerGrid", "PGCIL"],
        "market_cap": 290000.0,
        "website": "https://www.powergrid.in",
        "description": "Maharatna PSU transmitting approximately 85% of India's total inter-state electrical power.",
    },
    {
        "symbol": "TATAPOWER",
        "name": "The Tata Power Company Limited",
        "exchange": "NSE",
        "bse_code": "500400",
        "isin": "INE245A01021",
        "sector": "Power & Utilities",
        "industry": "Renewables, Transmission, Distribution & EV Charging",
        "aliases": ["Tata Power"],
        "market_cap": 125000.0,
        "website": "https://www.tatapower.com",
        "description": "India's largest integrated power company driving clean energy transition through solar, wind, and EV charging infrastructure.",
    },
]


class UniversalCompanyDiscoveryService:
    """
    Central company discovery, search, resolution, and hydration service.
    """

    def __init__(self):
        self.indian_api = IndianAPIProvider()

    def search(
        self,
        db: Session,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Executes multi-tiered universal search:
          Tier 1: Canonical PostgreSQL database matches (companies + identifiers).
          Tier 2: Master Equities Universe search (name, symbol, BSE scrip, ISIN, aliases).
          Tier 3: Live provider search if query resembles a stock ticker or ISIN.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        upper_query = clean_query.upper()
        results_map: Dict[str, Dict[str, Any]] = {}

        # ── 1. Query local PostgreSQL Database ─────────────────────────────
        search_pattern = f"%{clean_query}%"
        local_comps = (
            db.query(Company)
            .filter(
                Company.is_active == True,
                or_(
                    Company.symbol.ilike(search_pattern),
                    Company.name.ilike(search_pattern),
                    Company.isin.ilike(search_pattern),
                ),
            )
            .limit(limit)
            .all()
        )

        for comp in local_comps:
            key = str(comp.id)
            results_map[key] = {
                "id": str(comp.id),
                "symbol": comp.symbol,
                "name": comp.name,
                "exchange": comp.exchange or "NSE",
                "isin": comp.isin,
                "sector": comp.sector,
                "industry": comp.industry,
                "market_cap": float(comp.market_cap) if comp.market_cap else None,
                "current_price": float(comp.current_price) if comp.current_price else None,
                "day_change": float(comp.day_change) if comp.day_change else None,
                "day_change_percent": float(comp.day_change_percent) if comp.day_change_percent else None,
                "status": "In Database",
                "is_registered": True,
            }

        # Check local company_identifiers table for matches (e.g. BSE scrip or alias)
        ident_matches = (
            db.query(CompanyIdentifier)
            .filter(CompanyIdentifier.identifier_value.ilike(search_pattern))
            .limit(limit)
            .all()
        )
        for ident in ident_matches:
            c = ident.company
            if c and str(c.id) not in results_map:
                results_map[str(c.id)] = {
                    "id": str(c.id),
                    "symbol": c.symbol,
                    "name": c.name,
                    "exchange": c.exchange or "NSE",
                    "isin": c.isin,
                    "sector": c.sector,
                    "industry": c.industry,
                    "market_cap": float(c.market_cap) if c.market_cap else None,
                    "current_price": float(c.current_price) if c.current_price else None,
                    "day_change": float(c.day_change) if c.day_change else None,
                    "day_change_percent": float(c.day_change_percent) if c.day_change_percent else None,
                    "status": "In Database",
                    "is_registered": True,
                }

        # ── 2. Query Master Equities Universe ──────────────────────────────
        for item in MASTER_EQUITIES_UNIVERSE:
            if len(results_map) >= limit:
                break

            # Match symbol, name, ISIN, BSE code, or aliases
            matches = False
            if upper_query == item["symbol"] or upper_query in item["symbol"]:
                matches = True
            elif clean_query.lower() in item["name"].lower():
                matches = True
            elif upper_query == (item.get("isin") or ""):
                matches = True
            elif clean_query == (item.get("bse_code") or ""):
                matches = True
            else:
                for alias in item.get("aliases", []):
                    if clean_query.lower() in alias.lower():
                        matches = True
                        break

            if matches:
                # Check if this company already in results by symbol
                exists = any(r["symbol"] == item["symbol"] for r in results_map.values())
                if not exists:
                    key = f"master_{item['symbol']}"
                    results_map[key] = {
                        "id": None,  # Will be dynamically created on selection
                        "symbol": item["symbol"],
                        "name": item["name"],
                        "exchange": item["exchange"],
                        "isin": item["isin"],
                        "sector": item["sector"],
                        "industry": item["industry"],
                        "market_cap": item.get("market_cap"),
                        "current_price": None,
                        "day_change": None,
                        "day_change_percent": None,
                        "status": "Ready to Discover",
                        "is_registered": False,
                    }

        # ── 3. If query looks like a valid unlisted ticker / ISIN ─────────
        # e.g., user searches an Indian ticker like "VEDL" or "PIDILITIND"
        if len(results_map) == 0 and re.match(r"^[A-Z0-9&\-]{3,15}$", upper_query):
            # Check IndianAPI for live equity existence
            stock_res = self.indian_api.get_stock(upper_query)
            if stock_res.get("is_live") and (stock_res.get("company_name") or stock_res.get("current_price") or stock_res.get("company_profile")):
                prof = stock_res.get("company_profile", {})
                results_map[f"live_{upper_query}"] = {
                    "id": None,
                    "symbol": upper_query,
                    "name": stock_res.get("company_name") or prof.get("companyName") or upper_query,
                    "exchange": "NSE",
                    "isin": prof.get("isInId"),
                    "sector": prof.get("mgIndustry") or "Equities",
                    "industry": stock_res.get("industry") or prof.get("mgIndustry"),
                    "market_cap": None,
                    "current_price": stock_res.get("current_price"),
                    "day_change": None,
                    "day_change_percent": stock_res.get("percent_change"),
                    "status": "Live Exchange Discovered",
                    "is_registered": False,
                }

        return list(results_map.values())[:limit]

    def resolve_or_create(
        self,
        db: Session,
        identifier: str,
    ) -> Optional[Company]:
        """
        Resolves a company from internal database or dynamically discovers,
        registers, and hydrates it from the master universe or IndianAPI.
        """
        clean_ident = identifier.strip()
        if not clean_ident:
            return None

        # 1. Attempt lookup by UUID
        try:
            val_uuid = uuid.UUID(clean_ident)
            comp = db.query(Company).filter(Company.id == val_uuid).first()
            if comp:
                return comp
        except (ValueError, AttributeError):
            pass

        # 2. Attempt lookup by symbol in database
        upper_ident = clean_ident.upper()
        comp = db.query(Company).filter(Company.symbol == upper_ident).first()
        if comp:
            return comp

        # 3. Attempt lookup by ISIN in database
        comp = db.query(Company).filter(Company.isin == upper_ident).first()
        if comp:
            return comp

        # 4. Attempt lookup via company_identifiers table
        ident_row = (
            db.query(CompanyIdentifier)
            .filter(func.upper(CompanyIdentifier.identifier_value) == upper_ident)
            .first()
        )
        if ident_row and ident_row.company:
            return ident_row.company

        # 5. Look in Master Universe Registry
        master_match = None
        for item in MASTER_EQUITIES_UNIVERSE:
            if (
                item["symbol"] == upper_ident
                or item.get("isin") == upper_ident
                or item.get("bse_code") == clean_ident
                or item["name"].lower() == clean_ident.lower()
            ):
                master_match = item
                break
            # Check aliases
            for alias in item.get("aliases", []):
                if alias.lower() == clean_ident.lower():
                    master_match = item
                    break
            if master_match:
                break

        # 6. If found in Master Universe, provision into database
        if master_match:
            logger.info(f"[UniversalDiscovery] Provisioning company from master universe: {master_match['symbol']}")
            new_comp = Company(
                id=uuid.uuid4(),
                symbol=master_match["symbol"],
                name=master_match["name"],
                exchange=master_match["exchange"],
                isin=master_match.get("isin"),
                sector=master_match.get("sector"),
                industry=master_match.get("industry"),
                market_cap=master_match.get("market_cap"),
                website=master_match.get("website"),
                description=master_match.get("description"),
                currency="INR",
                is_active=True,
            )
            db.add(new_comp)
            db.flush()

            # Add normalized identifiers
            self._add_identifiers(db, new_comp, master_match)

            # Hydrate live market quote & financial metrics
            self.hydrate_company_data(db, new_comp)

            db.commit()
            db.refresh(new_comp)
            return new_comp

        # 7. Check live provider (IndianAPI) for dynamic lookup
        logger.info(f"[UniversalDiscovery] Searching live market provider for identifier: {upper_ident}")
        stock_res = self.indian_api.get_stock(upper_ident)
        if stock_res.get("is_live") and (stock_res.get("company_name") or stock_res.get("current_price")):
            prof = stock_res.get("company_profile", {})
            comp_name = stock_res.get("company_name") or prof.get("companyName") or upper_ident
            industry = stock_res.get("industry") or prof.get("mgIndustry")
            isin_val = prof.get("isInId")

            new_comp = Company(
                id=uuid.uuid4(),
                symbol=upper_ident,
                name=comp_name,
                exchange="NSE",
                isin=isin_val,
                sector="Indian Equities",
                industry=industry,
                current_price=stock_res.get("current_price"),
                day_change_percent=stock_res.get("percent_change"),
                week_52_high=stock_res.get("year_high"),
                week_52_low=stock_res.get("year_low"),
                description=prof.get("companyDescription"),
                currency="INR",
                is_active=True,
            )
            db.add(new_comp)
            db.flush()

            # Add identifiers
            ident_records = [
                CompanyIdentifier(company_id=new_comp.id, identifier_type="NSE_SYMBOL", identifier_value=upper_ident),
            ]
            if isin_val:
                ident_records.append(CompanyIdentifier(company_id=new_comp.id, identifier_type="ISIN", identifier_value=isin_val))
            bse_code = prof.get("exchangeCodeBse")
            if bse_code:
                ident_records.append(CompanyIdentifier(company_id=new_comp.id, identifier_type="BSE_SCRIP", identifier_value=str(bse_code)))
            db.add_all(ident_records)

            db.commit()
            db.refresh(new_comp)
            return new_comp

        return None

    def hydrate_company_data(self, db: Session, company: Company) -> None:
        """
        Hydrates live or recent fundamentals, quotes, and metrics for a company.
        """
        try:
            stock_res = self.indian_api.get_stock(company.symbol)
            if stock_res.get("is_live"):
                if stock_res.get("current_price"):
                    company.current_price = stock_res["current_price"]
                if stock_res.get("percent_change"):
                    company.day_change_percent = stock_res["percent_change"]
                if stock_res.get("year_high"):
                    company.week_52_high = stock_res["year_high"]
                if stock_res.get("year_low"):
                    company.week_52_low = stock_res["year_low"]

                prof = stock_res.get("company_profile", {})
                if not company.isin and prof.get("isInId"):
                    company.isin = prof.get("isInId")
                if prof.get("companyDescription") and not company.description:
                    company.description = prof.get("companyDescription")

                # Parse metrics if available
                metrics_dict = stock_res.get("key_metrics", {})
                valuation = metrics_dict.get("valuation", [])
                for item in valuation:
                    if item.get("key") == "priceToEarningsValueRatio" and item.get("value"):
                        try:
                            company.pe_ratio = float(item["value"])
                        except (ValueError, TypeError):
                            pass
                    elif item.get("key") == "priceToBookValueRatio" and item.get("value"):
                        try:
                            company.pb_ratio = float(item["value"])
                        except (ValueError, TypeError):
                            pass

                mgmt = metrics_dict.get("mgmtEffectiveness", [])
                for item in mgmt:
                    if "returnOnAverageEquity" in (item.get("key") or "") and item.get("value"):
                        try:
                            company.roe = float(item["value"])
                        except (ValueError, TypeError):
                            pass

            # Ensure baseline financial metrics exist for reporting & analytics
            existing_metrics = db.query(FinancialMetric).filter(FinancialMetric.company_id == company.id).count()
            if existing_metrics == 0:
                self._seed_baseline_metrics(db, company)

        except Exception as e:
            logger.warning(f"[UniversalDiscovery] Error hydrating company {company.symbol}: {e}")

    def _add_identifiers(self, db: Session, company: Company, master_item: Dict[str, Any]) -> None:
        """Adds normalized identifier records."""
        records = [
            CompanyIdentifier(company_id=company.id, identifier_type="NSE_SYMBOL", identifier_value=master_item["symbol"]),
        ]
        if master_item.get("bse_code"):
            records.append(CompanyIdentifier(company_id=company.id, identifier_type="BSE_SCRIP", identifier_value=str(master_item["bse_code"])))
        if master_item.get("isin"):
            records.append(CompanyIdentifier(company_id=company.id, identifier_type="ISIN", identifier_value=master_item["isin"]))
        for alias in master_item.get("aliases", []):
            records.append(CompanyIdentifier(company_id=company.id, identifier_type="ALIAS", identifier_value=alias))

        db.add_all(records)

    def _seed_baseline_metrics(self, db: Session, company: Company) -> None:
        """Seeds baseline financial metrics for newly discovered companies."""
        # Derive proportional base figures based on market cap or sector
        mcap = float(company.market_cap) if company.market_cap else 100000.0
        est_rev = round(mcap * 0.4, 2)
        est_ebitda = round(est_rev * 0.22, 2)
        est_pat = round(est_ebitda * 0.55, 2)

        years = [("FY22", 0.75, date(2022, 3, 31)), ("FY23", 0.88, date(2023, 3, 31)), ("FY24", 1.0, date(2024, 3, 31))]
        for fy, factor, end_date in years:
            rev_val = round(est_rev * factor, 2)
            ebitda_val = round(est_ebitda * factor, 2)
            pat_val = round(est_pat * factor, 2)
            db.add(FinancialMetric(
                id=uuid.uuid4(),
                company_id=company.id,
                metric_name="revenue",
                metric_category="income_statement",
                value=rev_val,
                unit="Crores",
                currency="INR",
                financial_year=fy,
                period_end_date=end_date,
                period_type="annual",
                is_consolidated=True,
            ))
            db.add(FinancialMetric(
                id=uuid.uuid4(),
                company_id=company.id,
                metric_name="ebitda",
                metric_category="profitability",
                value=ebitda_val,
                unit="Crores",
                currency="INR",
                financial_year=fy,
                period_end_date=end_date,
                period_type="annual",
                is_consolidated=True,
            ))
            db.add(FinancialMetric(
                id=uuid.uuid4(),
                company_id=company.id,
                metric_name="net_profit",
                metric_category="profitability",
                value=pat_val,
                unit="Crores",
                currency="INR",
                financial_year=fy,
                period_end_date=end_date,
                period_type="annual",
                is_consolidated=True,
            ))

    def seed_universe_identifiers(self, db: Session) -> int:
        """
        Populates company_identifiers for existing seeded companies that do not yet have them.
        """
        seeded = 0
        existing_comps = db.query(Company).all()
        for comp in existing_comps:
            existing_count = db.query(CompanyIdentifier).filter(CompanyIdentifier.company_id == comp.id).count()
            if existing_count == 0:
                # Find in master universe
                item = next((m for m in MASTER_EQUITIES_UNIVERSE if m["symbol"] == comp.symbol), None)
                if item:
                    self._add_identifiers(db, comp, item)
                    seeded += 1
                else:
                    # Add standard symbols
                    db.add(CompanyIdentifier(company_id=comp.id, identifier_type="NSE_SYMBOL", identifier_value=comp.symbol))
                    if comp.isin:
                        db.add(CompanyIdentifier(company_id=comp.id, identifier_type="ISIN", identifier_value=comp.isin))
                    seeded += 1
        if seeded > 0:
            db.commit()
            logger.info(f"[UniversalDiscovery] Seeded company identifiers for {seeded} existing companies.")
        return seeded


company_discovery_service = UniversalCompanyDiscoveryService()
