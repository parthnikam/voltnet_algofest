/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("_pb_users_auth_")

  // add field
  collection.fields.addAt(9, new Field({
    "hidden": false,
    "id": "number3104268214",
    "max": null,
    "min": null,
    "name": "wallet_reserved",
    "onlyInt": false,
    "presentable": false,
    "required": false,
    "system": false,
    "type": "number"
  }))

  // add field
  collection.fields.addAt(10, new Field({
    "autogeneratePattern": "",
    "hidden": false,
    "id": "text1727648867",
    "max": 0,
    "min": 0,
    "name": "public_key",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": false,
    "system": false,
    "type": "text"
  }))

  // add field
  collection.fields.addAt(11, new Field({
    "hidden": false,
    "id": "select3619035334",
    "maxSelect": 1,
    "name": "kyc_status",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "select",
    "values": [
      "pending",
      "verified",
      "blocked"
    ]
  }))

  // update field
  collection.fields.addAt(8, new Field({
    "hidden": false,
    "id": "number3215394072",
    "max": null,
    "min": null,
    "name": "wallet_balance",
    "onlyInt": false,
    "presentable": false,
    "required": true,
    "system": false,
    "type": "number"
  }))

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("_pb_users_auth_")

  // remove field
  collection.fields.removeById("number3104268214")

  // remove field
  collection.fields.removeById("text1727648867")

  // remove field
  collection.fields.removeById("select3619035334")

  // update field
  collection.fields.addAt(8, new Field({
    "hidden": false,
    "id": "number3215394072",
    "max": null,
    "min": null,
    "name": "wallet_ballance",
    "onlyInt": false,
    "presentable": false,
    "required": true,
    "system": false,
    "type": "number"
  }))

  return app.save(collection)
})
