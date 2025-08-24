# TFM_Vulnerabilidad_Inundaciones_Paiporta_Picanya

Este repositorio contiene los códigos de Python generados en el Trabajo Fin de Máster titulado "Diagnóstico y delimitación de áreas de riesgo de vulnerabilidad social frente a inundaciones en el Sur del área metropolitana de Valencia: caso de estudio de los municipios de Paiporta y Picanya", elaborado por David Cantó González. Los códigos se deben ejecutar en la consola de Python de QGIS. 

En el trabajo se propone una metodología de análisis mediante evaluación multicriterio a nivel de parcela catastral que se basa en la desagregación de estadísticas oficiales de carácter público y gratuito (procedentes del INE) a escala de sección censal. Esta metodología se ha aplicado para elaborar un diagnóstico de la vulnerabilidad socioeconómica frente al riesgo de inundaciones de la población de los municipios de Paiporta y Picanya (Valencia), gravemente afectados por la DANA de octubre de 2024. 

El script traspasar_datos_parcelas.py desagrega todos los datos existentes en la capa de secciones censales y los traspasa a las parcelas catastrales, en función de la sección en la que se encuentran y el número de viviendas que tiene cada parcela. Este código crea un campo llamado “proporcion” que calcula qué fracción de la población total de la sección corresponde a cada parcela, lo que sirve para determinar cómo distribuir proporcionalmente todos los datos que se desagregan. En realidad, viene a ser la relación entre: Población de la parcela / Población total de la sección censal. Para la ejecución del script, se necesita una capa de secciones censales con los códigos de sección (CUSEC) y las estadísticas que se pretenden desagregar; y una capa de parcelas catastrales con el código de parcela (REFCAT) y el dato de población por parcela.

El script normalizar_datos_parcelas.py normaliza las estadísticas desagregadas a escala de parcela de catastrales utilizando el método de estandarización min-max, que se caracteriza por conservar la proporcionalidad de los datos y ha sido ampliamente utilizado en la literatura de la materia.

## Autoría

Los códigos generados han sido desarrollados por David Cantó González, alumno del máster en Tecnologías de la Información Geográfica de la Universidad de Alcalá.
