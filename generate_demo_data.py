"""Genereer Family Maarssen demo-data CSV's — eenmalig uitvoeren."""
import csv

# ─────────────────────────────────────────────
# products.csv  (30 SKU's uit demo-dossier)
# ─────────────────────────────────────────────
products = [
    ("SKU-001","Friet diepvries (standaard)","kg", 10,"kg","low","wholesale",0.19,0.20,10,1,1),
    ("SKU-002","Raspatat diepvries","kg",10,"kg","low","wholesale",0.03,0.20,10,1,1),
    ("SKU-003","Rundburger patty","stuk",20,"stuk","low","wholesale",0.22,0.15,20,1,1),
    ("SKU-004","Kipburger filet","stuk",20,"stuk","low","wholesale",0.07,0.15,20,1,1),
    ("SKU-005","Falafelburger patty","stuk",20,"stuk","low","wholesale",0.03,0.15,20,1,1),
    ("SKU-006","Brioche burgerbun","stuk",24,"stuk","medium","bakery",0.28,0.10,24,1,1),
    ("SKU-007","Burger kaas slices","stuk",100,"stuk","medium","wholesale",0.15,0.10,100,1,2),
    ("SKU-008","Bacon strips","kg",1,"kg","medium","wholesale",0.009,0.10,1,1,2),
    ("SKU-009","IJsbergsla/bladmix","kg",1,"kg","high","fresh",0.018,0.10,1,1,1),
    ("SKU-010","Tomaat","kg",5,"kg","high","fresh",0.015,0.10,5,1,1),
    ("SKU-011","Komkommer","stuk",12,"stuk","high","fresh",0.04,0.10,12,1,1),
    ("SKU-012","Rode ui (vers)","kg",5,"kg","medium","fresh",0.006,0.10,5,1,2),
    ("SKU-013","Augurk schijfjes","kg",2.5,"kg","low","wholesale",0.003,0.10,2.5,1,7),
    ("SKU-014","Champignons","kg",3,"kg","high","fresh",0.006,0.10,3,1,1),
    ("SKU-015","Burger relish","kg",2.5,"kg","low","wholesale",0.002,0.10,2.5,1,7),
    ("SKU-016","Mayonaise","L",10,"L","medium","wholesale",0.010,0.10,10,1,7),
    ("SKU-017","Curry saus","L",10,"L","medium","wholesale",0.006,0.10,10,1,7),
    ("SKU-018","Ketchup","L",10,"L","medium","wholesale",0.004,0.10,10,1,7),
    ("SKU-019","Satésaus","L",5,"L","medium","wholesale",0.006,0.10,5,1,3),
    ("SKU-020","Knoflooksaus","L",5,"L","medium","wholesale",0.007,0.10,5,1,3),
    ("SKU-021","Chilisaus","L",5,"L","medium","wholesale",0.003,0.10,5,1,3),
    ("SKU-022","Van Dobben croquetten","stuk",40,"stuk","low","wholesale",0.10,0.15,40,1,2),
    ("SKU-023","Frikandellen","stuk",50,"stuk","low","wholesale",0.17,0.15,50,1,2),
    ("SKU-024","Kaassouffles","stuk",40,"stuk","low","wholesale",0.07,0.15,40,1,2),
    ("SKU-025","Kipnuggets","stuk",100,"stuk","low","wholesale",0.22,0.15,100,1,2),
    ("SKU-026","Bitterballen","stuk",100,"stuk","low","wholesale",0.12,0.15,100,1,2),
    ("SKU-027","Softijs mix","L",10,"L","medium","fresh",0.014,0.10,10,1,2),
    ("SKU-028","Milkshake base","L",10,"L","medium","fresh",0.028,0.10,10,1,2),
    ("SKU-029","Coca-Cola 330ml blik","stuk",24,"stuk","low","wholesale",0.20,0.15,24,1,3),
    ("SKU-030","Heineken blik","stuk",24,"stuk","low","beer",0.06,0.15,24,1,3),
]

with open("demo_data/products.csv","w",newline="",encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["sku_id","sku_name","base_unit","pack_qty","pack_unit",
                "perishability","supplier_type","demand_per_cover",
                "buffer_pct","min_stock","round_to_pack","lead_time_days"])
    w.writerows(products)

# ─────────────────────────────────────────────
# sales_history.csv  (exact uit demo-dossier)
# ─────────────────────────────────────────────
sales = [
    ("2026-03-23","Mon",175,2620,"steady"),
    ("2026-03-24","Tue",180,2700,"steady"),
    ("2026-03-25","Wed",240,3550,"woensdag fritesdag (promo)"),
    ("2026-03-26","Thu",190,2840,"steady"),
    ("2026-03-27","Fri",255,3820,"friday rush"),
    ("2026-03-28","Sat",285,4300,"weekend peak"),
    ("2026-03-29","Sun",195,2920,"later opening"),
    ("2026-03-30","Mon",170,2550,"post-weekend dip"),
    ("2026-03-31","Tue",185,2760,"steady"),
    ("2026-04-01","Wed",235,3460,"woensdag fritesdag (promo)"),
    ("2026-04-02","Thu",190,2820,"steady"),
    ("2026-04-03","Fri",260,3890,"friday rush"),
    ("2026-04-04","Sat",290,4380,"weekend peak"),
    ("2026-04-05","Sun",205,3080,"holiday uplift Easter"),
    ("2026-04-06","Mon",175,2580,"steady"),
    ("2026-04-07","Tue",185,2760,"steady"),
    ("2026-04-08","Wed",245,3600,"woensdag fritesdag (promo)"),
    ("2026-04-09","Thu",195,2900,"steady"),
    ("2026-04-10","Fri",265,3980,"weekend start"),
    ("2026-04-11","Sat",300,4500,"weekend partycatering"),
]

with open("demo_data/sales_history.csv","w",newline="",encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["date","weekday","covers","revenue_eur","note"])
    w.writerows(sales)

# ─────────────────────────────────────────────
# stock_count.csv  (exact uit demo-dossier)
# ─────────────────────────────────────────────
stock = [
    ("2026-04-10","SKU-001",18,"kg","frozen fries"),
    ("2026-04-10","SKU-002",6,"kg","raspatat"),
    ("2026-04-10","SKU-003",30,"stuk","beef patties"),
    ("2026-04-10","SKU-004",18,"stuk","chicken burgers"),
    ("2026-04-10","SKU-005",16,"stuk","falafel burgers"),
    ("2026-04-10","SKU-006",40,"stuk","brioche buns"),
    ("2026-04-10","SKU-007",60,"stuk","cheese slices"),
    ("2026-04-10","SKU-008",0.6,"kg","bacon"),
    ("2026-04-10","SKU-009",1.2,"kg","salad mix"),
    ("2026-04-10","SKU-010",3.0,"kg","tomatoes"),
    ("2026-04-10","SKU-011",8,"stuk","cucumbers"),
    ("2026-04-10","SKU-012",2.0,"kg","red onions"),
    ("2026-04-10","SKU-013",1.8,"kg","pickle bucket partial"),
    ("2026-04-10","SKU-014",1.2,"kg","mushrooms"),
    ("2026-04-10","SKU-015",1.5,"kg","burger relish bucket partial"),
    ("2026-04-10","SKU-016",6.0,"L","mayo remaining"),
    ("2026-04-10","SKU-017",4.5,"L","curry remaining"),
    ("2026-04-10","SKU-018",3.5,"L","ketchup remaining"),
    ("2026-04-10","SKU-019",2.5,"L","satay sauce remaining"),
    ("2026-04-10","SKU-020",2.0,"L","garlic sauce remaining"),
    ("2026-04-10","SKU-021",1.5,"L","chili sauce remaining"),
    ("2026-04-10","SKU-022",20,"stuk","croquettes in open box"),
    ("2026-04-10","SKU-023",70,"stuk","frikandel stock"),
    ("2026-04-10","SKU-024",15,"stuk","kaassouffles in open box"),
    ("2026-04-10","SKU-025",80,"stuk","nuggets in open box"),
    ("2026-04-10","SKU-026",60,"stuk","bitterballen in open box"),
    ("2026-04-10","SKU-027",8.0,"L","soft-ice mix left"),
    ("2026-04-10","SKU-028",8.0,"L","milkshake base left"),
    ("2026-04-10","SKU-029",36,"stuk","cola cans"),
    ("2026-04-10","SKU-030",24,"stuk","heineken cans"),
]

with open("demo_data/stock_count.csv","w",newline="",encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["date","sku_id","on_hand_qty","unit","note"])
    w.writerows(stock)

# ─────────────────────────────────────────────
# reservations.csv  (vooruitbestellingen + party platters)
# ─────────────────────────────────────────────
reservations = [
    ("2026-04-11","dinner",0,1,2,"sports team pre-order demo"),
    ("2026-04-12","lunch",10,0,0,"small group demo"),
    ("2026-04-12","dinner",15,0,0,"family group demo"),
    ("2026-04-13","dinner",0,0,0,"normal"),
    ("2026-04-14","dinner",0,0,0,"normal"),
    ("2026-04-15","dinner",0,0,0,"woensdag fritesdag no preorders"),
    ("2026-04-18","dinner",12,0,1,"large order demo"),
    ("2026-04-27","dinner",0,0,0,"Koningsdag placeholder"),
    ("2026-12-24","dinner",0,0,0,"Kerst placeholder"),
]

with open("demo_data/reservations.csv","w",newline="",encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["date","service","reserved_covers","party_platters_25","party_platters_50","note"])
    w.writerows(reservations)

# ─────────────────────────────────────────────
# events.csv  (covers + fries + desserts ratio multipliers)
# ─────────────────────────────────────────────
events = [
    ("2026-04-05","Pasen (dessert promo)","holiday",1.12,1.05,1.30,"Paas Sundae promo"),
    ("2026-04-08","Woensdag fritesdag","weekly_promo",1.06,1.15,1.00,"Expliciet in assortimentsfolder"),
    ("2026-04-11","Partycatering piek","event",1.08,1.05,1.00,"Covers uplift + planned platters"),
    ("2026-04-15","Woensdag fritesdag","weekly_promo",1.06,1.15,1.00,"Expliciet in assortimentsfolder"),
    ("2026-04-27","Koningsdag","holiday",1.20,1.10,1.05,"Aanname: mall footfall"),
    ("2026-07-15","Zomer (ijs uplift)","seasonal",1.05,1.00,1.25,"Aanname: warmer weer"),
    ("2026-10-25","Herfstvakantie","seasonal",1.08,1.05,1.05,"Aanname"),
    ("2026-12-24","Kerstavond","holiday",1.25,1.10,1.15,"Aanname: takeaway piek"),
    ("2026-12-31","Oudjaarsdag","holiday",1.30,1.10,1.10,"Aanname: party orders"),
]

with open("demo_data/events.csv","w",newline="",encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["date","event_name","event_type","covers_multiplier",
                "fries_ratio_multiplier","desserts_ratio_multiplier","notes"])
    w.writerows(events)

print("Family Maarssen data aangemaakt:")
print(f"  products.csv:      {len(products)} SKUs")
print(f"  sales_history.csv: {len(sales)} dagen")
print(f"  stock_count.csv:   {len(stock)} regels")
print(f"  reservations.csv:  {len(reservations)} regels")
print(f"  events.csv:        {len(events)} events")
