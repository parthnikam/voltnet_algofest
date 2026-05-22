/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_750742419")

  // add field
  collection.fields.addAt(2, new Field({
    "hidden": false,
    "id": "number380606668",
    "max": null,
    "min": null,
    "name": "tick",
    "onlyInt": false,
    "presentable": false,
    "required": false,
    "system": false,
    "type": "number"
  }))

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_750742419")

  // remove field
  collection.fields.removeById("number380606668")

  return app.save(collection)
})
