import chromadb
client = chromadb.HttpClient(host="localhost", port=8001)
print([c.name for c in client.list_collections()])