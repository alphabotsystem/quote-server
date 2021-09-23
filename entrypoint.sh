source /run/secrets/alpha-service/key
if [[ $PRODUCTION_MODE == "1" ]]
then
	python app/quote_server.py
else
	python -u app/quote_server.py
fi