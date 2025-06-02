from fastapi import APIRouter, HTTPException
from schemas.item import Item

router = APIRouter()
items = []

@router.get("/items", response_model=list[Item])
def get_items():
    return items

@router.post("/items", response_model=Item)
def create_item(item: Item):
    items.append(item)
    return item

@router.put("/items/{item_id}", response_model=Item)
def update_item(item_id: int, updated_item: Item):
    for idx, item in enumerate(items):
        if item.id == item_id:
            items[idx] = updated_item
            return updated_item
    raise HTTPException(status_code=404, detail="Item not found")

@router.delete("/items/{item_id}")
def delete_item(item_id: int):
    for idx, item in enumerate(items):
        if item.id == item_id:
            del items[idx]
            return {"detail": "Item deleted"}
    raise HTTPException(status_code=404, detail="Item not found")