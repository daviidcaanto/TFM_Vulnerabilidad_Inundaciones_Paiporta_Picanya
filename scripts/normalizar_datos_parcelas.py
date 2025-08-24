from qgis.core import QgsProject, QgsVectorFileWriter, QgsVectorLayer, QgsField
from qgis.PyQt.QtCore import QVariant
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

# Layer name and output path
layer_name = "Datos_Parcelas_Indice"
output_path = "C:/Users/Usuario/Desktop/MASTER/TFM/DEFINITIVO/Datos_Parcelas_Indice_normalizado.gpkg"

# Get the layer from project
layer = QgsProject.instance().mapLayersByName(layer_name)[0]

# Convert layer attributes to a dataframe
data = [feat.attributes() for feat in layer.getFeatures()]
fields = [field.name() for field in layer.fields()]
df = pd.DataFrame(data, columns=fields)

# Variables to normalize
variables_to_normalize = [
    'Tasa_feminidad', 'Menor5_%', 'Ind_envejecimiento', 'Pob_extranjera_%',
    'Tamaño_hogar', '%_Hogares_unip', 'Crecimiento_pob_%', 'Tasa_paro',
    'Densidad_pob', 'Bajos_estudios_%', 'Precio_alquiler',
    'planta_baja', 'vuln_equip', 'vuln_uso', 'garaje'
]
age_variable = 'ANTIGUEDAD'

# Replace zeros with 
antig_valid = df[age_variable].replace(0, np.nan)

# Check values that are valid in the antiguity column
if antig_valid.notna().sum() > 0:
    max_age = antig_valid.max()
    min_age = antig_valid.min()
    # Normalize the valid values
    df[age_variable + "_norm"] = (max_age - antig_valid) / (max_age - min_age)
    # Replace NaN with 0
    df[age_variable + "_norm"] = df[age_variable + "_norm"].fillna(0)
else:
    # If all values are zero or NaN, set normalized column to 0
    df[age_variable + "_norm"] = 0

# Apply min-max normalization 
scaler = MinMaxScaler()
df_normalized = pd.DataFrame(
    scaler.fit_transform(df[variables_to_normalize]),
    columns=[var + "_norm" for var in variables_to_normalize],
    index=df.index
)

# Add new normalized columns to the dataframe
for col in df_normalized.columns:
    df[col] = df_normalized[col]

# Export to geopackage
options = QgsVectorFileWriter.SaveVectorOptions()
options.driverName = "GPKG"
options.layerName = layer_name + "_normalizado"

_writer = QgsVectorFileWriter.writeAsVectorFormatV2(
    layer,
    output_path,
    QgsProject.instance().transformContext(),
    options
)

# Reload the exported layer
out_layer = QgsVectorLayer(f"{output_path}|layername={layer_name}_normalizado", "Datos normalizados", "ogr")
out_layer.startEditing()

# Add new fields to the output layer
new_fields = df_normalized.columns.tolist() + [age_variable + "_norm"]
for col in new_fields:
    if col not in [f.name() for f in out_layer.fields()]:
        out_layer.addAttribute(QgsField(col, QVariant.Double))
out_layer.updateFields()

# Fill new fields with normalized values
for i, feat in enumerate(out_layer.getFeatures()):
    for col in new_fields:
        value = df.loc[i, col]
        out_layer.changeAttributeValue(
            feat.id(),
            out_layer.fields().indexOf(col),
            float(value) if pd.notna(value) else None
        )

out_layer.commitChanges()

# Add the new layer to the QGIS project
QgsProject.instance().addMapLayer(out_layer)

print("Normalization completed and saved to:")
print(output_path)
