import scene_kit as kit
from schema_index import SchemaIndex
from twno_writer import Document, Obj, RawId

NAME = "tinted-shape"
SIZE = 400.0
SIDE = 220.0
VIEW_MODEL = "Teinte"
ACCENT_PROPERTY = "accent"
SHAPE_PROPERTY = "couleur"
ACCENT_COLOR = kit.AMBER
DEFAULT_COLOR = kit.TEAL
MARK_OFFSET = 150.0
VIEW_MODEL_RANK = 0
ACCENT_RANK = 0
SHAPE_RANK = 1


def bind_color(doc, property_rank):
    color_key = SchemaIndex.default().property_key("SolidColor", "colorValue")
    path = bytes((VIEW_MODEL_RANK, property_rank))
    doc.add(Obj("DataBindContext", propertyKey=color_key, sourcePathIds=path))


def build(bound=True):
    doc = Document()
    doc.add(Obj("Backboard"))
    doc.add(Obj("ViewModel", name=VIEW_MODEL))
    doc.add(Obj("ViewModelPropertyColor", name=ACCENT_PROPERTY))
    doc.add(Obj("ViewModelPropertyColor", name=SHAPE_PROPERTY))
    doc.add(Obj("ViewModelInstance", name="defaut", viewModelId=RawId(VIEW_MODEL_RANK)))
    doc.add(Obj("ViewModelInstanceColor", viewModelPropertyId=RawId(ACCENT_RANK), propertyValue=ACCENT_COLOR))
    doc.add(Obj("ViewModelInstanceColor", viewModelPropertyId=RawId(SHAPE_RANK), propertyValue=DEFAULT_COLOR))
    artboard = doc.add(Obj("Artboard", name="Forme teintee", width=SIZE, height=SIZE,
                           viewModelId=RawId(VIEW_MODEL_RANK)))
    node = doc.add(Obj("Node", name="centre", parent=artboard, x=SIZE / 2, y=SIZE / 2))
    kit.solid_shape(doc, node, "mark", "Ellipse", ACCENT_COLOR, x=MARK_OFFSET, y=-MARK_OFFSET, width=26.0, height=26.0)
    if bound:
        bind_color(doc, ACCENT_RANK)
    kit.solid_shape(doc, node, "forme", "Rectangle", DEFAULT_COLOR, width=SIDE, height=SIDE, cornerRadiusTL=36.0)
    if bound:
        bind_color(doc, SHAPE_RANK)
    return doc
