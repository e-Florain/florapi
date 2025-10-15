# Créer un environnement virtuel
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
pip3 install -r odoo_requirements.txt (à échanger avec votre propre requirements ds odoo18)


# florapi
curl -k -H "Content-Type: application/json" -H "x-api-key: m82zqBDyH8Y0IczAKwJRFTuandNrfNRuWfNKvwjEEbIryEAhQph5zHpC57AyBYbF" -XGET "http://127.0.0.1/getAdhpros"

curl -k -H "Content-Type: application/json" -H "x-api-key: m82zqBDyH8Y0IczAKwJRFTuandNrfNRuWfNKvwjEEbIryEAhQph5zHpC57AyBYbF" -XGET "http://127.0.0.1/getAdhs"

To access to swagger use http://127.0.0.1/swagger

### Launch Florapi as a service
cp florapi.service /etc/systemd/system \
chmod 644 /etc/systemd/system/florapi.service \
systemctl daemon-reload\
systemctl enable florapi.service \
systemctl start florapi.service