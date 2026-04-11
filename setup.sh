#!/bin/bash
# Setup script — eenmalig uitvoeren voor eerste gebruik
# Gebruik: bash setup.sh

echo "Installeren Python packages..."
pip install -r requirements.txt

echo "Demo-data controleren..."
if [ ! -f "demo_data/products.csv" ]; then
    echo "WAARSCHUWING: demo_data/products.csv ontbreekt"
fi

echo ""
echo "Setup klaar. Start de app met:"
echo "  streamlit run app.py"
