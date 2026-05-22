/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = new Collection({
    "createRule": null,
    "deleteRule": null,
    "fields": [
      {
        "autogeneratePattern": "[a-z0-9]{15}",
        "hidden": false,
        "id": "text3208210256",
        "max": 15,
        "min": 15,
        "name": "id",
        "pattern": "^[a-z0-9]+$",
        "presentable": false,
        "primaryKey": true,
        "required": true,
        "system": true,
        "type": "text"
      },
      {
        "cascadeDelete": false,
        "collectionId": "pbc_4092543785",
        "hidden": false,
        "id": "relation3320769076",
        "maxSelect": 1,
        "minSelect": 0,
        "name": "round",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "relation"
      },
      {
        "cascadeDelete": false,
        "collectionId": "_pb_users_auth_",
        "hidden": false,
        "id": "relation3479234172",
        "maxSelect": 1,
        "minSelect": 0,
        "name": "owner",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "relation"
      },
      {
        "hidden": false,
        "id": "select595663797",
        "maxSelect": 1,
        "name": "side",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "select",
        "values": [
          "buy",
          "sell"
        ]
      },
      {
        "hidden": false,
        "id": "number1198892646",
        "max": null,
        "min": null,
        "name": "quantity_kwh",
        "onlyInt": false,
        "presentable": false,
        "required": false,
        "system": false,
        "type": "number"
      },
      {
        "hidden": false,
        "id": "number114316413",
        "max": null,
        "min": null,
        "name": "remaining_kwh",
        "onlyInt": false,
        "presentable": false,
        "required": false,
        "system": false,
        "type": "number"
      },
      {
        "hidden": false,
        "id": "number2535906324",
        "max": null,
        "min": null,
        "name": "limit_price",
        "onlyInt": false,
        "presentable": false,
        "required": false,
        "system": false,
        "type": "number"
      },
      {
        "hidden": false,
        "id": "select3096409545",
        "maxSelect": 1,
        "name": "order_status",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "select",
        "values": [
          "open",
          "partially_filled",
          "filled",
          "rejected",
          "cancelled",
          "expired"
        ]
      },
      {
        "hidden": false,
        "id": "select1602912115",
        "maxSelect": 1,
        "name": "source",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "select",
        "values": [
          "simulator",
          "websocket",
          "api",
          "device"
        ]
      },
      {
        "autogeneratePattern": "",
        "hidden": false,
        "id": "text988650451",
        "max": 0,
        "min": 0,
        "name": "telemetry_hash",
        "pattern": "",
        "presentable": false,
        "primaryKey": false,
        "required": false,
        "system": false,
        "type": "text"
      },
      {
        "autogeneratePattern": "",
        "hidden": false,
        "id": "text2928148801",
        "max": 0,
        "min": 0,
        "name": "signature",
        "pattern": "",
        "presentable": false,
        "primaryKey": false,
        "required": false,
        "system": false,
        "type": "text"
      },
      {
        "autogeneratePattern": "",
        "hidden": false,
        "id": "text2909529734",
        "max": 0,
        "min": 0,
        "name": "rejection_reason",
        "pattern": "",
        "presentable": false,
        "primaryKey": false,
        "required": false,
        "system": false,
        "type": "text"
      },
      {
        "hidden": false,
        "id": "date261981154",
        "max": "",
        "min": "",
        "name": "expires_at",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "date"
      },
      {
        "hidden": false,
        "id": "autodate2990389176",
        "name": "created",
        "onCreate": true,
        "onUpdate": false,
        "presentable": false,
        "system": false,
        "type": "autodate"
      },
      {
        "hidden": false,
        "id": "autodate3332085495",
        "name": "updated",
        "onCreate": true,
        "onUpdate": true,
        "presentable": false,
        "system": false,
        "type": "autodate"
      }
    ],
    "id": "pbc_750742419",
    "indexes": [],
    "listRule": null,
    "name": "market_orders",
    "system": false,
    "type": "base",
    "updateRule": null,
    "viewRule": null
  });

  return app.save(collection);
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_750742419");

  return app.delete(collection);
})
