from qgis.core import *
from qgis.PyQt.QtCore import QVariant

def add_field(layer, name, field_type=QVariant.Double):
    """
    Add a new field to the layer if it does not already exist.

    Args:
        layer (QgsVectorLayer): Target vector layer.
        name (str): Name of the field to add.
        field_type (QVariant.Type): Field data type (default: Double).
    """
    existing_fields = [field.name() for field in layer.fields()]
    if name not in existing_fields:
        layer.dataProvider().addAttributes([QgsField(name, field_type)])
        layer.updateFields()
    return layer.fields().indexFromName(name)


def spatial_join(parcels_layer, sections_layer, demographic_fields):
    """
    Perform a spatial join between parcels and census sections.

    Args:
        parcels_layer (QgsVectorLayer): Layer with parcel geometries.
        sections_layer (QgsVectorLayer): Layer with section geometries and data.
        demographic_fields (list of str): Fields to transfer from sections.

    Returns:
        QgsVectorLayer: Joined memory layer.
    """
    joined_result = processing.run("qgis:joinattributesbylocation", {
        'INPUT': parcels_layer,
        'JOIN': sections_layer,
        'PREDICATE': [0],  # Intersects
        'JOIN_FIELDS': demographic_fields,
        'METHOD': 1,  # One-to-one (attributes from the first matching feature)
        'DISCARD_NONMATCHING': False,
        'OUTPUT': 'memory:joined_layer'
    })
    return joined_result['OUTPUT']


def safe_float(value):
    """Safely convert QVariant to float handling commas and empty values"""
    if value in [None, '']:
        return 0.0
    try:
        return float(str(value).replace(',', '.'))
    except:
        return 0.0


def run_geoprocess():
    """
    Perform a spatial join between census sections and cadastral parcels.
    Estimate demographic values per parcel and compute derived metrics
    such as area and population density. Keeps only essential attributes.
    """
    project = QgsProject.instance()

    # Load input layers
    sections_layer = next((l for l in project.mapLayersByName('Secciones_Datos')), None)
    parcels_layer = next((l for l in project.mapLayersByName('Datos_Parcelas')), None)

    if not sections_layer or not parcels_layer:
        print("Required layers not found.")
        return

    # Validate required fields
    required_fields = [
        'CUSEC', 'Pob_total', 'Pob_mujeres', 'Pob_hombres',
        'Pob_menor5', 'Pob_mayor65', 'Pob_menor15',
        'Pob_extranjera', 'Pob_2011', 'Pob_paro',
        'Pob_activa', 'Pob_bajos_estudios', 'Pob_mayor15',
        'Tamaño_hogar', '%_Hogares_unip', 'Precio_alquiler'
    ]
    for f in required_fields + ['REFCAT', 'pob_parcela']:
        layer = sections_layer if f in required_fields else parcels_layer
        if f not in [field.name() for field in layer.fields()]:
            print(f"Missing required field '{f}'")
            return

    # Demographic fields to transfer (excluding reference fields)
    exclude_fields = ['fid', 'CUSEC', 'CUMUN', 'NMUN', 'MUNICIPIO']
    demographic_fields = [f for f in sections_layer.fields().names() if f not in exclude_fields]
    
    # Perform spatial join
    joined_layer = spatial_join(parcels_layer, sections_layer, demographic_fields)
    if not joined_layer or not joined_layer.isValid():
        print("Error: Invalid joined layer")
        return

    # Transfer fields with no transformation
    direct_fields = ['Tamaño_hogar', '%_Hogares_unip', 'Precio_alquiler']
    cusec_dict = {}
    
    for feature in sections_layer.getFeatures():
        cusec = feature['CUSEC']
        cusec_dict[cusec] = {field: feature[field] for field in direct_fields if field in feature.fields().names()}

    # Fiels to be added
    fields_to_add = [
        'proporcion', 'area_km2',
        *[f'est_{f}' for f in demographic_fields if f not in direct_fields],
        *direct_fields,
        'Densidad_pob', 'Tasa_feminidad', 'Menor5_%',
        'Ind_envejecimiento', 'Pob_extranjera_%',
        'Crecimiento_pob_%', 'Tasa_paro', 'Bajos_estudios_%'
    ]
    
    field_indices = {}

    # Start editing the joined layer
    joined_layer.startEditing()

    try:
        # Add fields
        for field in fields_to_add:
            field_indices[field] = add_field(joined_layer, field)
        
        # Transfer direct fields (with no transformation) only if there's population
        for feature in joined_layer.getFeatures():
            fid = feature.id()
            cusec = feature['CUSEC']
            pob_parcela = safe_float(feature['pob_parcela'])

            if pob_parcela > 0 and cusec in cusec_dict:
                for field, value in cusec_dict[cusec].items():
                    joined_layer.changeAttributeValue(fid, field_indices[field], value)
            else:
                # If there's not population, establish 0 as value
                for field in direct_fields:
                    joined_layer.changeAttributeValue(fid, field_indices[field], 0.0)

        for feature in joined_layer.getFeatures():
            fid = feature.id()
            
            # Compute proportion: pob_parcela / Pob_total
            try:
                parcel_pop = safe_float(feature['pob_parcela'])
                section_total = safe_float(feature['Pob_total'])
                proportion = parcel_pop / section_total if section_total != 0 else 0.0
                joined_layer.changeAttributeValue(fid, field_indices['proporcion'], proportion)
            except Exception as e:
                print(f"Error calculating proportion: {str(e)}")
                proportion = 0.0

            # Calculate estimated demographic values 
            est_values = {}
            for f in demographic_fields:
                if f not in direct_fields:
                    try:
                        val = safe_float(feature[f])
                        estimated = val * proportion
                        est_values[f] = estimated
                        joined_layer.changeAttributeValue(fid, field_indices[f'est_{f}'], estimated)
                    except Exception as e:
                        print(f"Error estimating {f}: {str(e)}")
                        est_values[f] = 0.0

            # Calculate area in km²
            try:
                area_km2 = feature.geometry().area() / 1000000
                joined_layer.changeAttributeValue(fid, field_indices['area_km2'], area_km2)
            except Exception as e:
                print(f"Error calculating area: {str(e)}")
                area_km2 = 0.0

            # Calculate rates
            try:
                total = est_values.get('Pob_total', 0.0)
                area_km2_val = area_km2 if area_km2 > 0 else 1.0
                
                densidad = total / area_km2_val
                
                mujeres = est_values.get('Pob_mujeres', 0.0)
                hombres = est_values.get('Pob_hombres', 1.0)
                tasa_fem = (mujeres / hombres * 100) if hombres != 0 else 0.0
                
                menor5 = est_values.get('Pob_menor5', 0.0)
                menor5_pct = (menor5 / total * 100) if total != 0 else 0.0
                
                mayor65 = est_values.get('Pob_mayor65', 0.0)
                menor15 = est_values.get('Pob_menor15', 1.0)
                ind_env = (mayor65 / menor15 * 100) if menor15 != 0 else 0.0
                
                extranjera = est_values.get('Pob_extranjera', 0.0)
                extranjera_pct = (extranjera / total * 100) if total != 0 else 0.0
                
                pob_2011 = est_values.get('Pob_2011', 0.0)
                crecimiento = ((total - pob_2011) / pob_2011 * 100) if pob_2011 != 0 else 0.0
                
                paro = est_values.get('Pob_paro', 0.0)
                activa = est_values.get('Pob_activa', 1.0)
                tasa_paro = (paro / activa * 100) if activa != 0 else 0.0
                
                bajos_est = est_values.get('Pob_bajos_estudios', 0.0)
                mayor15 = est_values.get('Pob_mayor15', 1.0)
                bajos_est_pct = (bajos_est / mayor15 * 100) if mayor15 != 0 else 0.0

                joined_layer.changeAttributeValue(fid, field_indices['Densidad_pob'], densidad)
                joined_layer.changeAttributeValue(fid, field_indices['Tasa_feminidad'], tasa_fem)
                joined_layer.changeAttributeValue(fid, field_indices['Menor5_%'], menor5_pct)
                joined_layer.changeAttributeValue(fid, field_indices['Ind_envejecimiento'], ind_env)
                joined_layer.changeAttributeValue(fid, field_indices['Pob_extranjera_%'], extranjera_pct)
                joined_layer.changeAttributeValue(fid, field_indices['Crecimiento_pob_%'], crecimiento)
                joined_layer.changeAttributeValue(fid, field_indices['Tasa_paro'], tasa_paro)
                joined_layer.changeAttributeValue(fid, field_indices['Bajos_estudios_%'], bajos_est_pct)
            except Exception as e:
                print(f"Error calculating rates: {str(e)}")

        # Clean up fields 
        useful_fields = [
            'REFCAT', 'ANTIGUEDAD', 'N_PLANTAS', 'USO', 'num_viv', 
            'pob_parcela', 'proporcion', 'area_km2', 'Tamaño_hogar',
            '%_Hogares_unip', 'Precio_alquiler',
            *[f'est_{f}' for f in demographic_fields if f not in direct_fields],
            'Densidad_pob', 'Tasa_feminidad', 'Menor5_%',
            'Ind_envejecimiento', 'Pob_extranjera_%',
            'Crecimiento_pob_%', 'Tasa_paro', 'Bajos_estudios_%'
        ]
        
        for field in joined_layer.fields():
            if field.name() not in useful_fields:
                idx = joined_layer.fields().indexFromName(field.name())
                joined_layer.deleteAttribute(idx)
        joined_layer.updateFields()

        # Commit changes
        if not joined_layer.commitChanges():
            print("Commit failed; rolling back.")
            joined_layer.rollBack()
            return

    except Exception as e:
        print(f"Error during editing session: {e}")
        try:
            joined_layer.rollBack()
        except Exception:
            pass
        return


    # Save results
    output_path = project.homePath() + "/Datos_Desagregados.gpkg"
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = "Datos_Parcelas"

    error_code, error_message = QgsVectorFileWriter.writeAsVectorFormatV2(
        joined_layer, output_path, QgsProject.instance().transformContext(), options)
    
    if error_code == QgsVectorFileWriter.NoError:
        print(f"Process completed. File saved to: {output_path}")
        iface.addVectorLayer(output_path, "Parcel Data", "ogr")
    else:
        print(f"Error saving file: {error_message}")

# Run the process
run_geoprocess()