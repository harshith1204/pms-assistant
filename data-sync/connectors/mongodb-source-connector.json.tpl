{
  "name": "mongodb-source-connector",
  "config": {
    "connector.class": "com.mongodb.kafka.connect.MongoSourceConnector",
    "connection.uri": "${MONGODB_URI}",
    "database": "${MONGODB_DATABASE}",
    "change.stream.full.document": "updateLookup",
    "publish.full.document.only": "false",
    "pipeline": "[{\"$match\": { \"operationType\": { \"$in\": [\"insert\", \"update\", \"replace\", \"delete\"] }, \"ns.coll\": { \"$in\": [\"page\", \"workItem\", \"project\", \"cycle\", \"module\", \"epic\"] } }}]",
    "topic.namespace.map": "{\"*\":\"${KAFKA_TOPIC}\"}",
    "copy.existing": "true",
    "copy.existing.namespace.regex": "${MONGODB_DATABASE}\\\.(page|workItem|project|cycle|module|epic)",
    "key.converter": "org.apache.kafka.connect.storage.StringConverter",
    "key.converter.schemas.enable": "false",
    "value.converter": "org.apache.kafka.connect.json.JsonConverter",
    "value.converter.schemas.enable": "false"
  }
}
