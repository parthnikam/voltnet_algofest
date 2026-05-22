/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const nodes = app.findCollectionByNameOrId("nodes")
  nodes.fields.addAt(16, new Field({
    "hidden": false,
    "id": "number_wallet_balance_v2",
    "max": null,
    "min": null,
    "name": "wallet_balance",
    "onlyInt": false,
    "presentable": false,
    "required": false,
    "system": false,
    "type": "number"
  }))
  app.save(nodes)

  const orders = app.findCollectionByNameOrId("market_orders")
  orders.fields.addAt(3, new Field({
    "cascadeDelete": false,
    "collectionId": "pbc_3598433047",
    "hidden": false,
    "id": "relation_order_node_v2",
    "maxSelect": 1,
    "minSelect": 0,
    "name": "node",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "relation"
  }))
  orders.fields.addAt(4, new Field({
    "autogeneratePattern": "",
    "hidden": false,
    "id": "text_order_owner_user_v2",
    "max": 0,
    "min": 0,
    "name": "owner_user_id",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": false,
    "system": false,
    "type": "text"
  }))
  orders.fields.addAt(5, new Field({
    "hidden": false,
    "id": "number_order_tick_v2",
    "max": null,
    "min": null,
    "name": "tick",
    "onlyInt": true,
    "presentable": false,
    "required": false,
    "system": false,
    "type": "number"
  }))
  app.save(orders)
}, (app) => {
  const orders = app.findCollectionByNameOrId("market_orders")
  orders.fields.removeById("relation_order_node_v2")
  orders.fields.removeById("text_order_owner_user_v2")
  orders.fields.removeById("number_order_tick_v2")
  app.save(orders)

  const nodes = app.findCollectionByNameOrId("nodes")
  nodes.fields.removeById("number_wallet_balance_v2")
  app.save(nodes)
})
