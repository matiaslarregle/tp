
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import base64
import io
import xlsxwriter
import random
import warnings
warnings.filterwarnings('ignore')
import openai
from openai import OpenAI
import os
import time

st.set_page_config(
    page_title="Oferta Académica Inteligente",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

def configurar_openrouter():
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key="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"
    )

class AnalizadorTextoIA:
    def __init__(self):
        self.client = configurar_openrouter()

    def analizar_patrones_demanda(self, df_historico, df_predicciones):
        try:
            resumen_completo = self._generar_resumen_historico_completo(df_historico)

            resumen_predicciones = f"Predicciones actuales: {len(df_predicciones)} materias. "
            resumen_predicciones += f"Rango de alumnos estimados: {df_predicciones['pred_final'].min()} - {df_predicciones['pred_final'].max()}."

            prompt = f"Como experto en análisis académico, analiza estos datos COMPLETOS de oferta académica: {resumen_completo} {resumen_predicciones} Proporciona: 1. Tres insights clave sobre patrones de demanda, 2. Dos recomendaciones estratégicas, 3. Un alerta sobre posibles riesgos. Responde en español de manera concisa."

            response = self.client.chat.completions.create(
                model="openai/gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"Error en análisis IA: {str(e)}"

    def _generar_resumen_historico_completo(self, df_historico):
        if df_historico.empty:
            return "No hay datos históricos disponibles."

        resumen = "DATOS HISTÓRICOS COMPLETOS: "

        # Información básica
        resumen += f"Período: {df_historico['CUATRIMESTRE'].min()} a {df_historico['CUATRIMESTRE'].max()}. "
        resumen += f"Total registros: {len(df_historico)}. "
        resumen += f"Materias distintas: {df_historico['MATERIA'].nunique()}. "

        # Estadísticas de comisiones
        if 'COMISIONES' in df_historico.columns:
            resumen += f"Comisiones por materia (promedio): {df_historico['COMISIONES'].mean():.1f}. "
            resumen += f"Máximo de comisiones en una materia: {df_historico['COMISIONES'].max()}. "

        # Estadísticas de alumnos
        resumen += f"Alumnos por materia (promedio): {df_historico['TOTAL_ALUMNOS'].mean():.1f}. "
        resumen += f"Máximo histórico de alumnos: {df_historico['TOTAL_ALUMNOS'].max()} en {df_historico.loc[df_historico['TOTAL_ALUMNOS'].idxmax(), 'MATERIA']}. "

        # Estadísticas de rendimiento académico
        if 'PROMOCIONO' in df_historico.columns:
            tasa_promocion = (df_historico['PROMOCIONO'].sum() / df_historico['TOTAL_ALUMNOS'].sum()) * 100
            tasa_abandono = (df_historico['ABANDONO'].sum() / df_historico['TOTAL_ALUMNOS'].sum()) * 100
            if 'INSUFICIENTE' in df_historico.columns:
                tasa_insuficiente = (df_historico['INSUFICIENTE'].sum() / df_historico['TOTAL_ALUMNOS'].sum()) * 100
                resumen += f"Tasa de insuficientes histórica: {tasa_insuficiente:.1f}%. "

            resumen += f"Tasa de promoción histórica: {tasa_promocion:.1f}%. "
            resumen += f"Tasa de abandono histórica: {tasa_abandono:.1f}%. "

        # Top materias por demanda
        top_demanda = df_historico.groupby('MATERIA')['TOTAL_ALUMNOS'].sum().nlargest(3)
        resumen += "Top 3 materias históricas por demanda: " + ", ".join([f"{materia} ({alumnos} alumnos)" for materia, alumnos in top_demanda.items()]) + ". "

        # Materias con mayor tasa de promoción
        if 'PROMOCIONO' in df_historico.columns:
            df_historico['TASA_PROMOCION'] = (df_historico['PROMOCIONO'] / df_historico['TOTAL_ALUMNOS']) * 100
            top_promocion = df_historico[df_historico['TOTAL_ALUMNOS'] > 10].nlargest(3, 'TASA_PROMOCION')
            if not top_promocion.empty:
                resumen += "Materias con mayor tasa de promoción: " + ", ".join([f"{row['MATERIA']} ({row['TASA_PROMOCION']:.1f}%)" for _, row in top_promocion.head(3).iterrows()]) + ". "

        return resumen

    def generar_recomendaciones_personalizadas(self, materia, datos_materia):
        try:
            prompt = f"Para la materia: {materia}. Datos: Alumnos estimados: {datos_materia.get('alumnos_estimados', 'N/A')}, Carga horaria: {datos_materia.get('carga_horaria', 'N/A')} horas, Modalidad: {datos_materia.get('modalidad', 'N/A')}. Como experto en planificación académica, proporciona 2-3 recomendaciones específicas para optimizar la oferta. Responde en español, sé conciso."

            response = self.client.chat.completions.create(
                model="openai/gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"Error generando recomendaciones: {str(e)}"

class ChatbotOfertaAcademica:
    def __init__(self, df_historico, df_predicciones):
        self.client = configurar_openrouter()
        self.historial = []
        self.df_historico = df_historico
        self.df_predicciones = df_predicciones

    def enviar_mensaje(self, mensaje_usuario, oferta_actual=None):
        try:
            contexto_sistema = self._preparar_contexto_completo(oferta_actual)

            # MEJORAR DETECCIÓN DE CONSULTAS ESPECÍFICAS SOBRE DATOS HISTÓRICOS
            consulta_especifica = self._detectar_consulta_especifica(mensaje_usuario)

            self.historial.append({"role": "user", "content": mensaje_usuario})

            system_prompt = f"Eres un asistente especializado en análisis de oferta académica universitaria. {contexto_sistema} INSTRUCCIONES CRÍTICAS: 1. SIEMPRE debes basarte EXCLUSIVAMENTE en los datos históricos reales proporcionados en el contexto. 2. NUNCA inventes números o datos que no estén en el contexto. 3. Si no hay datos para un período específico, debes indicarlo CLARAMENTE diciendo 'No hay datos reales disponibles para [materia] en [período]'. 4. Si el usuario pregunta por datos que no están en el contexto, NO los inventes. 5. Usa SOLO la información proporcionada en el contexto. Responde en español de manera clara y concisa. Sé práctico y orientado a soluciones."

            mensajes = [
                {"role": "system", "content": system_prompt}
            ] + self.historial[-6:]

            response = self.client.chat.completions.create(
                model="openai/gpt-3.5-turbo",
                messages=mensajes,
                max_tokens=500,
                temperature=0.3  # Reducir temperatura para mayor precisión
            )

            respuesta = response.choices[0].message.content

            # VERIFICAR Y CORREGIR DATOS HISTÓRICOS EN LA RESPUESTA
            respuesta = self._corregir_datos_historicos(respuesta, mensaje_usuario)

            self.historial.append({"role": "assistant", "content": respuesta})

            return respuesta

        except Exception as e:
            return f"Error en el chatbot: {str(e)}"

    def _detectar_consulta_especifica(self, mensaje):
        mensaje_lower = mensaje.lower()
        if any(termino in mensaje_lower for termino in ['alumno', 'estudiante', 'cantidad', 'cuántos', 'cuantos', 'matriculados', 'número', 'numero']):
            if any(termino in mensaje_lower for termino in ['2020', '2021', '2022', '2023', '2024']):
                return "consulta_historica_especifica"
        return "consulta_general"

    def _corregir_datos_historicos(self, respuesta, pregunta_original):
        try:
            pregunta_lower = pregunta_original.lower()

            # Buscar materia en la pregunta
            materia_consultada = None
            for materia in self.df_historico['MATERIA'].unique():
                if materia.lower() in pregunta_lower:
                    materia_consultada = materia
                    break

            if not materia_consultada:
                return respuesta

            # Buscar año y cuatrimestre en la pregunta
            año_consultado = None
            cuatrimestre_consultado = None

            for año in ['2020', '2021', '2022', '2023', '2024']:
                if año in pregunta_original:
                    año_consultado = año
                    break

            if '1c' in pregunta_lower:
                cuatrimestre_consultado = '1C'
            elif '2c' in pregunta_lower:
                cuatrimestre_consultado = '2C'

            # Buscar datos reales
            datos_reales = self._obtener_datos_reales_especificos(materia_consultada, año_consultado, cuatrimestre_consultado)

            if datos_reales and datos_reales != "No hay datos específicos":
                # Verificar si la respuesta contiene datos incorrectos
                if any(palabra in respuesta.lower() for palabra in ['estimad', 'aproximad', 'probable', 'posible', '280', '300', '250']):
                    # Integrar los datos de forma natural
                    datos_formateados = self._formatear_datos_naturalmente(datos_reales, materia_consultada)
                    respuesta = respuesta + " " + datos_formateados

            elif datos_reales == "No hay datos específicos":
                # Si no hay datos pero la respuesta está inventando números
                if any(str(num) in respuesta for num in [280, 300, 250, 200, 150]):
                    respuesta = "No hay datos reales disponibles para la consulta específica. " + respuesta

            return respuesta

        except Exception as e:
            return respuesta

    def _formatear_datos_naturalmente(self, datos_reales, materia):
        try:
            # Parsear los datos para extraer información específica
            if ":" in datos_reales:
                partes = datos_reales.split(":")
                if len(partes) >= 2:
                    periodo = partes[0].strip().replace("**", "").replace("*", "")
                    info_alumnos = partes[1].strip()

                    # Extraer número de alumnos
                    alumnos = ""
                    if "alumnos" in info_alumnos:
                        alumnos_part = info_alumnos.split("alumnos")[0].strip()
                        alumnos = alumnos_part

                    # Extraer comisiones
                    comisiones = ""
                    if "comisiones" in info_alumnos:
                        comisiones_part = info_alumnos.split("comisiones")[0]
                        if "(" in comisiones_part:
                            comisiones = comisiones_part.split("(")[-1].strip()

                    # Extraer tasa de promoción
                    tasa_promocion = ""
                    if "Tasa promocion:" in info_alumnos:
                        tasa_part = info_alumnos.split("Tasa promocion:")[1]
                        tasa_promocion = tasa_part.split("%")[0].strip() + "%"

                    # Construir respuesta natural
                    respuesta_natural = "En " + periodo + ", " + materia + " tuvo " + alumnos + " alumnos"
                    if comisiones:
                        respuesta_natural += " distribuidos en " + comisiones + " comision(es)"
                    if tasa_promocion:
                        respuesta_natural += ", con una tasa de promocion del " + tasa_promocion
                    respuesta_natural += "."

                    return respuesta_natural

            # Si no se puede parsear, devolver los datos originales pero sin el formato crudo
            return "Los registros historicos indican: " + datos_reales.replace("**", "").replace(":", " fue")

        except Exception as e:
            return "Segun los registros: " + datos_reales

    def _obtener_datos_reales_especificos(self, materia, año, cuatrimestre):
        try:
            # Filtrar datos
            filtro = self.df_historico['MATERIA'] == materia

            if año:
                filtro = filtro & (self.df_historico['CUATRIMESTRE'].str.contains(str(año)))

            if cuatrimestre:
                filtro = filtro & (self.df_historico['CUATRIMESTRE'].str.contains(cuatrimestre))

            datos_filtrados = self.df_historico[filtro]

            if datos_filtrados.empty:
                return "No hay datos específicos"

            # Devolver solo el primer resultado para hacerlo más legible
            fila = datos_filtrados.iloc[0]
            resultado = fila['CUATRIMESTRE'] + ": " + str(fila['TOTAL_ALUMNOS']) + " alumnos"

            if 'COMISIONES' in fila and not pd.isna(fila['COMISIONES']):
                resultado += " (" + str(fila['COMISIONES']) + " comisiones)"

            if 'PROMOCIONO' in fila and not pd.isna(fila['PROMOCIONO']) and fila['TOTAL_ALUMNOS'] > 0:
                tasa_promocion = (fila['PROMOCIONO'] / fila['TOTAL_ALUMNOS']) * 100
                resultado += " - Tasa promocion: " + f"{tasa_promocion:.1f}" + "%"

            return resultado

        except Exception as e:
            return "Error obteniendo datos: " + str(e)

    def _preparar_contexto_completo(self, oferta_actual):
        contexto = "CONTEXTO COMPLETO DEL SISTEMA ACADÉMICO - DATOS REALES: "

        # AGREGAR DATOS HISTÓRICOS ESPECÍFICOS MÁS RELEVANTES
        contexto += "DATOS HISTÓRICOS REALES (EJEMPLOS DE ALGUNAS MATERIAS): "

        # Obtener algunas materias clave con sus datos reales más recientes
        materias_clave = ["Álgebra", "Análisis Matemático I", "Introducción a la Programación", "Herramientas computacionales"]
        for materia in materias_clave:
            datos_materia = self._obtener_datos_reales_resumen(materia)
            if datos_materia and datos_materia != "No hay datos":
                contexto += f"{materia}: {datos_materia}. "

        contexto += "DATOS HISTÓRICOS DETALLADOS: "

        if self.df_historico.empty:
            contexto += "No hay datos históricos disponibles. "
        else:
            contexto += f"Período histórico completo: {self.df_historico['CUATRIMESTRE'].min()} a {self.df_historico['CUATRIMESTRE'].max()}. "
            contexto += f"Total de registros históricos: {len(self.df_historico)}. "
            contexto += f"Materias distintas en histórico: {self.df_historico['MATERIA'].nunique()}. "

            if 'COMISIONES' in self.df_historico.columns:
                contexto += f"Promedio de comisiones por materia: {self.df_historico['COMISIONES'].mean():.1f}. "
                contexto += f"Máximo de comisiones en una materia: {self.df_historico['COMISIONES'].max()}. "

            contexto += f"Promedio histórico de alumnos por materia: {self.df_historico['TOTAL_ALUMNOS'].mean():.1f}. "

            max_historico_idx = self.df_historico['TOTAL_ALUMNOS'].idxmax()
            max_historico = self.df_historico.loc[max_historico_idx]
            contexto += f"MÁXIMO HISTÓRICO REAL: {max_historico['MATERIA']} en {max_historico['CUATRIMESTRE']} con {max_historico['TOTAL_ALUMNOS']} alumnos"
            if 'COMISIONES' in max_historico:
                contexto += f" ({max_historico['COMISIONES']} comisiones)"
            contexto += ". "

            if 'PROMOCIONO' in self.df_historico.columns:
                total_alumnos_historicos = self.df_historico['TOTAL_ALUMNOS'].sum()
                tasa_promocion = (self.df_historico['PROMOCIONO'].sum() / total_alumnos_historicos) * 100
                tasa_abandono = (self.df_historico['ABANDONO'].sum() / total_alumnos_historicos) * 100
                if 'REGULAR' in self.df_historico.columns:
                    tasa_regular = (self.df_historico['REGULAR'].sum() / total_alumnos_historicos) * 100
                    contexto += f"Tasa de regularidad histórica: {tasa_regular:.1f}%. "
                if 'INSUFICIENTE' in self.df_historico.columns:
                    tasa_insuficiente = (self.df_historico['INSUFICIENTE'].sum() / total_alumnos_historicos) * 100
                    contexto += f"Tasa de insuficientes histórica: {tasa_insuficiente:.1f}%. "

                contexto += f"Tasas históricas: Promoción: {tasa_promocion:.1f}%, Abandono: {tasa_abandono:.1f}%. "

            top_demanda_historica = self.df_historico.groupby('MATERIA')['TOTAL_ALUMNOS'].sum().nlargest(5)
            contexto += "TOP 5 MATERIAS POR DEMANDA HISTÓRICA: " + ", ".join([f"{materia} ({alumnos} alumnos)" for materia, alumnos in top_demanda_historica.items()]) + ". "

            if 'PROMOCIONO' in self.df_historico.columns:
                self.df_historico['TASA_PROMOCION'] = (self.df_historico['PROMOCIONO'] / self.df_historico['TOTAL_ALUMNOS']) * 100
                top_rendimiento = self.df_historico[self.df_historico['TOTAL_ALUMNOS'] > 10].nlargest(3, 'TASA_PROMOCION')
                if not top_rendimiento.empty:
                    contexto += "MATERIAS CON MEJOR RENDIMIENTO: " + ", ".join([f"{row['MATERIA']} ({row['TASA_PROMOCION']:.1f}% promoción)" for _, row in top_rendimiento.iterrows()]) + ". "

        contexto += "DATOS DE PREDICCIÓN ACTUAL: "
        contexto += f"Materias en predicción: {len(self.df_predicciones)}. "
        contexto += f"Rango de alumnos estimados: {self.df_predicciones['pred_final'].min()} - {self.df_predicciones['pred_final'].max()}. "
        contexto += f"Promedio de alumnos estimados: {self.df_predicciones['pred_final'].mean():.1f}. "

        top_predicciones = self.df_predicciones.nlargest(5, 'pred_final')
        contexto += "TOP 5 PREDICCIONES ACTUALES: " + ", ".join([f"{row['MATERIA']} ({row['pred_final']} alumnos)" for _, row in top_predicciones.iterrows()]) + ". "

        if oferta_actual and not oferta_actual.get('resumen', {}).get('error', False):
            contexto += self._preparar_contexto_oferta(oferta_actual)
        else:
            contexto += "OFERTA ACTUAL: El usuario aún no ha generado una oferta académica válida. Puedes ayudarle con análisis de datos históricos y predicciones."

        return contexto

    def _preparar_contexto_oferta(self, oferta_actual):
        contexto = "OFERTA ACADÉMICA GENERADA: "

        resumen = oferta_actual.get('resumen', {})
        contexto += f"RESUMEN: {resumen.get('total_materias', 0)} materias, {resumen.get('total_comisiones', 0)} comisiones. "
        contexto += f"Presencial: {resumen.get('total_comisiones_presencial', 0)}, Virtual: {resumen.get('total_comisiones_virtual', 0)}. "
        contexto += f"Alumnos: {resumen.get('total_alumnos', 0):,}. Ocupación: {resumen.get('utilizacion_sistema', 0):.1f}%. "
        contexto += f"Sedes: {resumen.get('sedes_utilizadas', 0)}."

        # AGREGAR INFORMACIÓN ESPECÍFICA POR MATERIA
        contexto += "DETALLE POR MATERIA: "
        materias_contadas = {}

        # Contar comisiones por materia en la oferta actual
        for año, materias_año in oferta_actual.get('oferta_por_año', {}).items():
            for materia_info in materias_año:
                nombre_materia = materia_info['materia']
                comisiones_totales = materia_info['comisiones_totales']
                if nombre_materia not in materias_contadas:
                    materias_contadas[nombre_materia] = 0
                materias_contadas[nombre_materia] += comisiones_totales

        # Agregar las materias más relevantes al contexto
        for materia, comisiones in list(materias_contadas.items())[:10]:  # Limitar para no sobrecargar
            contexto += f"{materia}: {comisiones} comisiones. "

        solapamientos = oferta_actual.get('solapamientos', [])
        if solapamientos:
            contexto += f"SOLAPAMIENTOS: {len(solapamientos)} detectados. "
        else:
            contexto += "Sin solapamientos. "

        recomendaciones = oferta_actual.get('recomendaciones', [])
        if recomendaciones:
            contexto += f"RECOMENDACIONES: {len(recomendaciones)} sugerencias del sistema. "

        return contexto

    def _obtener_datos_reales_resumen(self, materia):
        try:
            datos_materia = self.df_historico[self.df_historico['MATERIA'] == materia]
            if datos_materia.empty:
                return "No hay datos"

            ultimo_periodo = datos_materia.iloc[-1]
            return f"Último período {ultimo_periodo['CUATRIMESTRE']}: {ultimo_periodo['TOTAL_ALUMNOS']} alumnos"

        except:
            return "No hay datos"

    def obtener_comisiones_oferta_actual(self, oferta_actual, materia_nombre):
        if not oferta_actual or oferta_actual.get('resumen', {}).get('error', False):
            return 0

        total_comisiones = 0
        for año, materias_año in oferta_actual.get('oferta_por_año', {}).items():
            for materia_info in materias_año:
                if materia_info['materia'] == materia_nombre:
                    total_comisiones += materia_info['comisiones_totales']

        return total_comisiones

    def obtener_datos_materia_historica(self, materia_nombre):
        if self.df_historico.empty:
            return "No hay datos históricos disponibles."

        datos_materia = self.df_historico[self.df_historico['MATERIA'] == materia_nombre]
        if datos_materia.empty:
            return f"No se encontraron datos históricos REALES para la materia '{materia_nombre}'."

        resultado = "DATOS HISTORICOS REALES PARA " + materia_nombre.upper() + " "

        # Ordenar por cuatrimestre
        datos_materia = datos_materia.sort_values('CUATRIMESTRE')

        for _, fila in datos_materia.iterrows():
            resultado += f"• **{fila['CUATRIMESTRE']}**: {fila['TOTAL_ALUMNOS']} alumnos"
            if 'COMISIONES' in fila and not pd.isna(fila['COMISIONES']):
                resultado += f" ({fila['COMISIONES']} comisiones)"

            # Agregar información de rendimiento si está disponible
            if 'PROMOCIONO' in fila and not pd.isna(fila['PROMOCIONO']) and fila['TOTAL_ALUMNOS'] > 0:
                tasa_promocion = (fila['PROMOCIONO'] / fila['TOTAL_ALUMNOS']) * 100
                resultado += f" - Tasa promoción: {tasa_promocion:.1f}%"

            resultado += " "

        # Estadísticas resumen
        promedio_alumnos = datos_materia['TOTAL_ALUMNOS'].mean()
        max_alumnos = datos_materia['TOTAL_ALUMNOS'].max()
        min_alumnos = datos_materia['TOTAL_ALUMNOS'].min()
        total_registros = len(datos_materia)

        resultado += f"**📈 RESUMEN ESTADÍSTICO:**"
        resultado += f"• Promedio histórico: {promedio_alumnos:.1f} alumnos/cuatrimestre"
        resultado += f"• Mínimo histórico: {min_alumnos} alumnos"
        resultado += f"• Máximo histórico: {max_alumnos} alumnos"
        resultado += f"• Total de registros: {total_registros} cuatrimestres"

        # Tendencias
        if total_registros > 1:
            primer_valor = datos_materia.iloc[0]['TOTAL_ALUMNOS']
            ultimo_valor = datos_materia.iloc[-1]['TOTAL_ALUMNOS']
            variacion = ((ultimo_valor - primer_valor) / primer_valor) * 100
            resultado += f"• Tendencia: {variacion:+.1f}% desde {datos_materia.iloc[0]['CUATRIMESTRE']}"

        return resultado

    def analizar_eficiencia_oferta(self, oferta_actual):
        if not oferta_actual or oferta_actual.get('resumen', {}).get('error', False):
            return "No hay oferta actual para analizar."

        analisis = "ANÁLISIS DE EFICIENCIA - OFERTA ACTUAL: "
        resumen = oferta_actual.get('resumen', {})

        utilizacion = resumen.get('utilizacion_sistema', 0)
        if utilizacion > 90:
            analisis += "ALTA OCUPACIÓN: Excelente uso de recursos (>90%). "
        elif utilizacion > 70:
            analisis += "BUENA OCUPACIÓN: Uso eficiente de recursos (70-90%). "
        elif utilizacion > 50:
            analisis += "OCUPACIÓN MODERADA: Espacio para optimización (50-70%). "
        else:
            analisis += "BAJA OCUPACIÓN: Recursos subutilizados (<50%). "

        total_comisiones = resumen.get('total_comisiones', 1)
        comisiones_virtual = resumen.get('total_comisiones_virtual', 0)
        porcentaje_virtual = (comisiones_virtual / total_comisiones) * 100 if total_comisiones > 0 else 0

        if porcentaje_virtual > 60:
            analisis += f"ALTA VIRTUALIDAD: {porcentaje_virtual:.1f}% comisiones virtuales. "
        elif porcentaje_virtual > 30:
            analisis += f"EQUILIBRIO MODALIDAD: {porcentaje_virtual:.1f}% virtual. "
        else:
            analisis += f"BAJA VIRTUALIDAD: {porcentaje_virtual:.1f}% virtual. "

        return analisis

st.markdown('''
<style>
.main-header { font-size: 2.5rem; color: #215086; font-weight: bold; margin-bottom: 1rem; }
.secondary-header { font-size: 1.8rem; color: #215086; font-weight: bold; margin-bottom: 1rem; }
.metric-card { background-color: #f4f5ff; padding: 1rem; border-radius: 10px; border-left: 4px solid #215086; }
.info-box { background-color: #d9daea; padding: 1rem; border-radius: 8px; border: 1px solid #215086; }
.conflicto-grave { background-color: #ffebee; border-left: 4px solid #f44336; padding: 1rem; margin: 5px 0; border-radius: 4px; }
.horario-box { background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 10px; margin: 5px 0; }
.chat-container { background-color: #f8f9fa; border-radius: 10px; padding: 20px; margin: 10px 0; }
.user-message { background-color: #215086; color: white; padding: 10px; border-radius: 10px; margin: 5px 0; text-align: right; }
.bot-message { background-color: #e9ecef; color: #333; padding: 10px; border-radius: 10px; margin: 5px 0; }
.sidebar-logo { text-align: center; margin-bottom: 2rem; }
.sidebar-logo img { max-width: 80%; border-radius: 10px; }
</style>
''', unsafe_allow_html=True)

@st.cache_data
def cargar_datos_reales():
    try:
        # Cargar predicciones
        try:
            predicciones_df = pd.read_csv('predicciones_2024_2_allmaterias.csv')
            st.success("✅ Datos de predicciones cargados correctamente")
        except Exception as e:
            st.error(f"❌ Error cargando predicciones_2024_2_allmaterias.csv: {e}")
            st.error("El archivo de predicciones es requerido para el funcionamiento del sistema.")
            st.stop()

        # Cargar datos históricos REALES
        try:
            historico_df = pd.read_csv('archivo (6).csv')

            # Verificar que tenemos las columnas mínimas necesarias
            columnas_requeridas = ['MATERIA', 'CUATRIMESTRE', 'TOTAL_ALUMNOS']
            columnas_faltantes = [col for col in columnas_requeridas if col not in historico_df.columns]

            if columnas_faltantes:
                st.error(f"❌ Error: Faltan columnas críticas en archivo.csv: {columnas_faltantes}")
                st.error("Las columnas mínimas requeridas son: MATERIA, CUATRIMESTRE, TOTAL_ALUMNOS")
                st.stop()

            st.success("✅ Datos históricos cargados correctamente")

        except Exception as e:
            st.error(f"❌ Error cargando archivo.csv: {e}")
            st.error("El archivo histórico es requerido para el funcionamiento del sistema.")
            st.stop()

        return historico_df, predicciones_df

    except Exception as e:
        st.error(f"❌ Error general cargando datos: {e}")
        st.error("No se pueden cargar los datos requeridos. Verifica que los archivos existan en la ruta correcta.")
        st.stop()

# ELIMINAR COMPLETAMENTE LA FUNCIÓN generar_datos_fallback
# Ya no se generarán datos de ejemplo

sedes = [
    {"nombre": "Casa de la Cultura Adrogué", "salones": 5, "salones_disponibles": list(range(1, 6)), "dias_semana": "16:00-22:00", "sabado": None},
    {"nombre": "Escuela Nro 5", "salones": 5, "salones_disponibles": list(range(1, 6)), "dias_semana": "19:00-23:00", "sabado": None},
    {"nombre": "Nacional", "salones": 20, "salones_disponibles": list(range(1, 21)), "dias_semana": "19:00-23:00", "sabado": "09:00-13:00"},
    {"nombre": "Campus UNaB", "salones": 20, "salones_disponibles": list(range(1, 21)), "dias_semana": "08:00-23:00", "sabado": "09:00-13:00"}
]

# Carga horaria real basada en el plan de estudios de Big Data
carga_horaria = {
    "Herramientas computacionales": 96, "Análisis Matemático I": 96, "Taller de Ciencia, Tecnología y Sociedad": 64,
    "Inglés": 48, "Administración": 64, "Álgebra": 96, "Introducción a la Programación": 96, "Análisis Matemático II": 96,
    "Economía": 64, "Introducción al Análisis Contable y Financiero": 64, "Probabilidad y Estadística": 96,
    "Recolección de Datos y Análisis Primario de la Información": 96, "Algoritmos y estructuras de Datos": 96,
    "Metodologías de investigación": 64, "Inferencia Estadística y reconocimiento de patrones": 96, "Gestión de Datos": 96,
    "Análisis Multivariado": 64, "Visualización de la información": 64, "Modelado y Simulación": 96, "Programación Avanzada": 96,
    "Inteligencia Artificial": 96, "Taller I - Big Data y las políticas públicas": 96, "Análisis en Redes Sociales": 64,
    "Técnicas de Investigación de Mercado": 64, "Formulación y evaluación de proyectos tecnológicos": 64, "Computación en la Nube": 64,
    "Taller II _x0096_ Big Data y la Salud": 96, "Comercio Electrónico": 64, "Seminario Final": 48, "Práctica Profesional Supervisada (PPS)": 48
}

correlativas = {
    "Herramientas computacionales": {"Cursado": [], "Aprobado": []},
    "Análisis Matemático I": {"Cursado": [], "Aprobado": []},
    "Taller de Ciencia, Tecnología y Sociedad": {"Cursado": [], "Aprobado": []},
    "Inglés": {"Cursado": [], "Aprobado": []},
    "Administración": {"Cursado": ["Taller de Ciencia, Tecnología y Sociedad"], "Aprobado": []},
    "Álgebra": {"Cursado": ["Análisis Matemático I"], "Aprobado": []},
    "Introducción a la Programación": {"Cursado": ["Herramientas computacionales"], "Aprobado": []},
    "Análisis Matemático II": {"Cursado": ["Análisis Matemático I"], "Aprobado": []},
    "Economía": {"Cursado": ["Administración"], "Aprobado": ["Taller de Ciencia, Tecnología y Sociedad"]},
    "Introducción al Análisis Contable y Financiero": {"Cursado": ["Administración"], "Aprobado": []},
    "Probabilidad y Estadística": {"Cursado": ["Álgebra"], "Aprobado": []},
    "Recolección de Datos y Análisis Primario de la Información": {"Cursado": ["Introducción a la Programación", "Herramientas computacionales"], "Aprobado": []},
    "Algoritmos y estructuras de Datos": {"Cursado": ["Recolección de Datos y Análisis Primario de la Información"], "Aprobado": ["Introducción a la Programación"]},
    "Metodologías de investigación": {"Cursado": ["Administración"], "Aprobado": []},
    "Inferencia Estadística y reconocimiento de patrones": {"Cursado": ["Probabilidad y Estadística"], "Aprobado": []},
    "Gestión de Datos": {"Cursado": ["Recolección de Datos y Análisis Primario de la Información"], "Aprobado": []},
    "Análisis Multivariado": {"Cursado": ["Algoritmos y estructuras de Datos"], "Aprobado": ["Análisis Matemático I"]},
    "Visualización de la información": {"Cursado": ["Recolección de Datos y Análisis Primario de la Información"], "Aprobado": []},
    "Modelado y Simulación": {"Cursado": ["Gestión de Datos", "Algoritmos y estructuras de Datos"], "Aprobado": []},
    "Programación Avanzada": {"Cursado": ["Gestión de Datos"], "Aprobado": []},
    "Inteligencia Artificial": {"Cursado": ["Inferencia Estadística y reconocimiento de patrones"], "Aprobado": []},
    "Taller I - Big Data y las políticas públicas": {"Cursado": [], "Aprobado": []},
    "Análisis en Redes Sociales": {"Cursado": ["Visualización de la información"], "Aprobado": []},
    "Técnicas de Investigación de Mercado": {"Cursado": [], "Aprobado": []},
    "Formulación y evaluación de proyectos tecnológicos": {"Cursado": [], "Aprobado": []},
    "Computación en la Nube": {"Cursado": ["Programación Avanzada"], "Aprobado": ["Gestión de Datos"]},
    "Taller II _x0096_ Big Data y la Salud": {"Cursado": ["Taller I - Big Data y las políticas públicas"], "Aprobado": []},
    "Comercio Electrónico": {"Cursado": ["Técnicas de Investigación de Mercado"], "Aprobado": []},
    "Seminario Final": {"Cursado": ["Modelado y Simulación", "Visualización de la información", "Programación Avanzada", "Análisis Multivariado", "Inteligencia Artificial", "Análisis en Redes Sociales", "Taller I - Big Data y las políticas públicas", "Formulación y evaluación de proyectos tecnológicos"], "Aprobado": []},
    "Práctica Profesional Supervisada (PPS)": {"Cursado": ["Modelado y Simulación", "Visualización de la información", "Programación Avanzada", "Análisis Multivariado", "Inteligencia Artificial", "Análisis en Redes Sociales", "Taller I - Big Data y las políticas públicas", "Formulación y evaluación de proyectos tecnológicos"], "Aprobado": []}
}

class SistemaPrediccion:
    def __init__(self, df_historico, df_predicciones):
        self.df_historico = df_historico
        self.df_predicciones = df_predicciones

    def predecir_demanda(self, materia):
        pred = self.df_predicciones[self.df_predicciones['MATERIA'] == materia]['pred_final']
        return pred.iloc[0] if not pred.empty else 30

class SistemaRecomendacion:
    def __init__(self, df_historico, correlativas):
        self.df_historico = df_historico
        self.correlativas = correlativas

    def generar_recomendaciones_optimizacion(self, oferta_actual):
        recomendaciones = []
        try:
            for año, materias in oferta_actual.get('oferta_por_año', {}).items():
                for materia in materias:
                    capacidad_comision = materia.get('capacidad_comision', 40)
                    capacidad_total = capacidad_comision * materia.get('comisiones_totales', 1)
                    demanda = materia.get('alumnos_estimados', 0)
                    nombre_materia = materia.get('materia', 'Materia desconocida')
                    porcentaje_sobrecapacidad = (capacidad_total / demanda * 100) if demanda > 0 else 0

                    if capacidad_total > demanda * 1.5:
                        recomendaciones.append({
                            'tipo': 'SOBRECAPACIDAD',
                            'materia': nombre_materia,
                            'mensaje': f'Reducir comisiones en {nombre_materia}: Capacidad {capacidad_total} vs Demanda {demanda} ({porcentaje_sobrecapacidad:.1f}% de capacidad)',
                            'prioridad': 'media',
                            'capacidad_total': capacidad_total,
                            'demanda': demanda,
                            'porcentaje_sobrecapacidad': porcentaje_sobrecapacidad,
                            'comisiones_actuales': materia.get('comisiones_totales', 1),
                            'comisiones_recomendadas': max(1, (demanda + capacidad_comision - 1) // capacidad_comision)
                        })

                    elif capacidad_total < demanda * 0.8:
                        recomendaciones.append({
                            'tipo': 'SUBCAPACIDAD',
                            'materia': nombre_materia,
                            'mensaje': f'Aumentar comisiones en {nombre_materia}: Demanda {demanda} vs Capacidad {capacidad_total}',
                            'prioridad': 'alta',
                            'capacidad_total': capacidad_total,
                            'demanda': demanda,
                            'comisiones_actuales': materia.get('comisiones_totales', 1),
                            'comisiones_recomendadas': max(1, (demanda + capacidad_comision - 1) // capacidad_comision)
                        })

            resumen = oferta_actual.get('resumen', {})
            total_virtual = resumen.get('total_comisiones_virtual', 0)
            total_presencial = resumen.get('total_comisiones_presencial', 0)
            total_comisiones = total_virtual + total_presencial

            if total_comisiones > 0:
                porcentaje_virtual = (total_virtual / total_comisiones) * 100
                if porcentaje_virtual > 70:
                    recomendaciones.append({
                        'tipo': 'MODALIDAD',
                        'materia': 'SISTEMA',
                        'mensaje': f'Alto porcentaje virtual ({porcentaje_virtual:.1f}%). Considerar equilibrio modalidades.',
                        'prioridad': 'baja',
                        'porcentaje_virtual': porcentaje_virtual
                    })
                elif porcentaje_virtual < 30:
                    recomendaciones.append({
                        'tipo': 'MODALIDAD',
                        'materia': 'SISTEMA',
                        'mensaje': f'Bajo porcentaje virtual ({porcentaje_virtual:.1f}%). Considerar aumentar oferta virtual.',
                        'prioridad': 'baja',
                        'porcentaje_virtual': porcentaje_virtual
                    })

        except Exception as e:
            st.warning(f"Error generando recomendaciones: {e}")

        return recomendaciones

class GeneradorHorarios:
    def __init__(self, sedes, carga_horaria):
        self.sedes = sedes
        self.carga_horaria = carga_horaria
        self.horarios_ocupados = self._inicializar_estructura_ocupacion_completa()

    def _inicializar_estructura_ocupacion_completa(self):
        estructura = {}
        for sede in self.sedes:
            estructura[sede['nombre']] = {}
            for salon in sede['salones_disponibles']:
                estructura[sede['nombre']][salon] = {
                    'Lunes': {f"{h:02d}:{m:02d}": None for h in range(8, 24) for m in [0, 30]},
                    'Martes': {f"{h:02d}:{m:02d}": None for h in range(8, 24) for m in [0, 30]},
                    'Miércoles': {f"{h:02d}:{m:02d}": None for h in range(8, 24) for m in [0, 30]},
                    'Jueves': {f"{h:02d}:{m:02d}": None for h in range(8, 24) for m in [0, 30]},
                    'Viernes': {f"{h:02d}:{m:02d}": None for h in range(8, 24) for m in [0, 30]},
                    'Sábado': {f"{h:02d}:{m:02d}": None for h in range(8, 14) for m in [0, 30]}
                }
        return estructura

    def optimizar_asignacion_horarios(self, materias_info, salones_activos, ratio_global):
        self.horarios_ocupados = self._inicializar_estructura_ocupacion_completa()
        materias_ordenadas = sorted(materias_info, key=lambda x: x.get('alumnos_estimados', 0), reverse=True)
        asignaciones_optimizadas = []
        for materia_info in materias_ordenadas:
            materia = materia_info.get('materia', '')
            comisiones = materia_info.get('comisiones_totales', 1)
            modalidad = materia_info.get('modalidad', 'Presencial')

            if modalidad == "Mixta" and ratio_global > 0:
                comisiones_presencial = comisiones
                comisiones_virtual = max(1, comisiones_presencial // ratio_global)
                asignaciones_virtuales = self._generar_horarios_virtuales_optimizados(materia, comisiones_virtual)
                asignaciones_optimizadas.extend(asignaciones_virtuales)
                asignaciones_presenciales = self._generar_horarios_presenciales_optimizados(
                    materia, comisiones_presencial, materia_info.get('carga_horaria', 64),
                    salones_activos
                )
                asignaciones_optimizadas.extend(asignaciones_presenciales)
            elif modalidad == "Virtual":
                asignaciones_virtuales = self._generar_horarios_virtuales_optimizados(materia, comisiones)
                asignaciones_optimizadas.extend(asignaciones_virtuales)
            else:
                asignaciones_presenciales = self._generar_horarios_presenciales_optimizados(
                    materia, comisiones, materia_info.get('carga_horaria', 64),
                    salones_activos
                )
                asignaciones_optimizadas.extend(asignaciones_presenciales)
        return asignaciones_optimizadas

    def _generar_horarios_virtuales_optimizados(self, materia, comisiones):
        horarios_virtuales = [
            {"dias": ["Lunes", "Miércoles"], "horario": "19:00-21:00", "turno": "Noche"},
            {"dias": ["Martes", "Jueves"], "horario": "19:00-21:00", "turno": "Noche"},
            {"dias": ["Sábado"], "horario": "09:00-13:00", "turno": "Mañana"}
        ]
        asignaciones = []
        for i in range(comisiones):
            horario_elegido = horarios_virtuales[i % len(horarios_virtuales)]
            horarios_clase = [f"{dia} {horario_elegido['horario']}" for dia in horario_elegido['dias']]
            asignaciones.append({
                'materia': materia, 'comision': i + 1, 'sede': 'PLATAFORMA VIRTUAL', 'salon': 'Aula Virtual',
                'turno': horario_elegido['turno'], 'horarios_clases': horarios_clase, 'duracion_total': len(horario_elegido['dias']) * 2
            })
        return asignaciones

    def _generar_horarios_presenciales_optimizados(self, materia, comisiones, horas_totales, salones_activos):
        turnos_disponibles = self._generar_turnos_segun_horas(horas_totales)
        asignaciones = []
        comisiones_asignadas = 0
        for i in range(comisiones):
            turno_elegido = turnos_disponibles[i % len(turnos_disponibles)]
            patron = turno_elegido['patron']
            sede, salon, patron_ajustado = self._buscar_salon_disponible_avanzado(patron, salones_activos, materia)
            if sede is None:
                for turno_alternativo in turnos_disponibles:
                    if turno_alternativo != turno_elegido:
                        patron_alternativo = turno_alternativo['patron']
                        sede, salon, patron_ajustado = self._buscar_salon_disponible_avanzado(patron_alternativo, salones_activos, materia)
                        if sede is not None:
                            turno_elegido = turno_alternativo
                            break
                if sede is None:
                    st.error(f"Imposible asignar horario: No se encontró salón disponible para {materia} después de múltiples intentos")
                    continue
            horarios_comision = [f"{dia} {horario} (Salón {salon})" for dia, horario in patron_ajustado]
            if not self._registrar_horarios_ocupados_avanzado(sede, salon, patron_ajustado, materia, comisiones_asignadas + 1):
                st.error(f"Error crítico: No se pudieron registrar horarios para {materia} en {sede} salón {salon}")
                continue
            asignaciones.append({
                'materia': materia, 'comision': comisiones_asignadas + 1, 'sede': sede, 'salon': salon,
                'turno': turno_elegido['turno'], 'horarios_clases': horarios_comision,
                'duracion_total': sum([4 if "22:00" in horario or "23:00" in horario else 2 for _, horario in patron_ajustado])
            })
            comisiones_asignadas += 1
        if comisiones_asignadas < comisiones:
            st.warning(f"Solo se pudieron asignar {comisiones_asignadas} de {comisiones} comisiones para {materia}")
        return asignaciones

    def _generar_turnos_segun_horas(self, horas_totales):
        patrones_por_turno = {
            'Mañana': {
                48: [[("Lunes", "08:00-10:00"), ("Miércoles", "08:00-10:00")]],
                64: [[("Lunes", "08:00-12:00")], [("Martes", "08:00-12:00")]],
                96: [[("Lunes", "08:00-12:00"), ("Miércoles", "08:00-10:00")]]
            },
            'Tarde': {
                48: [[("Lunes", "14:00-16:00"), ("Miércoles", "14:00-16:00")]],
                64: [[("Lunes", "14:00-18:00")], [("Martes", "14:00-18:00")]],
                96: [[("Lunes", "14:00-18:00"), ("Miércoles", "14:00-16:00")]]
            },
            'Noche': {
                48: [[("Lunes", "18:00-20:00"), ("Miércoles", "18:00-20:00")]],
                64: [[("Lunes", "18:00-22:00")], [("Martes", "18:00-22:00")]],
                96: [[("Lunes", "18:00-22:00"), ("Miércoles", "18:00-20:00")]]
            }
        }
        turnos_generados = []
        for turno in ["Mañana", "Tarde", "Noche"]:
            if turno in patrones_por_turno and horas_totales in patrones_por_turno[turno]:
                for patron in patrones_por_turno[turno][horas_totales]:
                    turnos_generados.append({'turno': turno, 'patron': patron})
        if not turnos_generados:
            turnos_generados.append({'turno': 'Noche', 'patron': [("Lunes", "18:00-22:00"), ("Miércoles", "18:00-20:00")]})
        return turnos_generados

    def _buscar_salon_disponible_avanzado(self, patron_horarios, salones_activos, materia):
        sedes_disponibles = [sede for sede in self.sedes if sede['nombre'] in salones_activos]
        for sede in sedes_disponibles:
            salones = sede.get('salones_disponibles', list(range(1, sede['salones'] + 1)))
            for salon in salones:
                if self._patron_completamente_disponible(sede['nombre'], salon, patron_horarios):
                    return sede['nombre'], salon, patron_horarios
        for sede in sedes_disponibles:
            salones = sede.get('salones_disponibles', list(range(1, sede['salones'] + 1)))
            for salon in salones:
                patron_alternativo = self._generar_patron_alternativo(patron_horarios)
                if patron_alternativo and self._patron_completamente_disponible(sede['nombre'], salon, patron_alternativo):
                    return sede['nombre'], salon, patron_alternativo
        return None, None, None

    def _patron_completamente_disponible(self, sede, salon, patron_horarios):
        for dia, horario in patron_horarios:
            if not self._horario_disponible(sede, salon, dia, horario): return False
        return True

    def _horario_disponible(self, sede, salon, dia, horario_str):
        try:
            if sede not in self.horarios_ocupados or salon not in self.horarios_ocupados[sede]: return True
            inicio_str, fin_str = horario_str.split('-')
            inicio_h, inicio_m = map(int, inicio_str.split(':'))
            fin_h, fin_m = map(int, fin_str.split(':'))
            hora_actual = inicio_h
            minuto_actual = inicio_m
            while hora_actual < fin_h or (hora_actual == fin_h and minuto_actual < fin_m):
                slot_key = f"{hora_actual:02d}:{minuto_actual:02d}"
                if self.horarios_ocupados[sede][salon][dia].get(slot_key) is not None: return False
                minuto_actual += 30
                if minuto_actual >= 60:
                    minuto_actual = 0
                    hora_actual += 1
            return True
        except Exception as e:
            st.error(f"Error verificando disponibilidad: {e}")
            return False

    def _registrar_horarios_ocupados_avanzado(self, sede, salon, patron_horarios, materia, comision):
        try:
            if sede not in self.horarios_ocupados: self.horarios_ocupados[sede] = {}
            if salon not in self.horarios_ocupados[sede]:
                self.horarios_ocupados[sede][salon] = {
                    'Lunes': {f"{h:02d}:{m:02d}": None for h in range(8, 24) for m in [0, 30]},
                    'Martes': {f"{h:02d}:{m:02d}": None for h in range(8, 24) for m in [0, 30]},
                    'Miércoles': {f"{h:02d}:{m:02d}": None for h in range(8, 24) for m in [0, 30]},
                    'Jueves': {f"{h:02d}:{m:02d}": None for h in range(8, 24) for m in [0, 30]},
                    'Viernes': {f"{h:02d}:{m:02d}": None for h in range(8, 24) for m in [0, 30]},
                    'Sábado': {f"{h:02d}:{m:02d}": None for h in range(8, 14) for m in [0, 30]}
                }
            for dia, horario_str in patron_horarios:
                inicio_str, fin_str = horario_str.split('-')
                inicio_h, inicio_m = map(int, inicio_str.split(':'))
                fin_h, fin_m = map(int, fin_str.split(':'))
                hora_actual = inicio_h
                minuto_actual = inicio_m
                while hora_actual < fin_h or (hora_actual == fin_h and minuto_actual < fin_m):
                    slot_key = f"{hora_actual:02d}:{minuto_actual:02d}"
                    self.horarios_ocupados[sede][salon][dia][slot_key] = f"{materia}_C{comision}"
                    minuto_actual += 30
                    if minuto_actual >= 60:
                        minuto_actual = 0
                        hora_actual += 1
            return True
        except Exception as e:
            st.error(f"Error registrando horarios avanzado: {e}")
            return False

    def _generar_patron_alternativo(self, patron_original):
        alternativas = []
        for dia, horario in patron_original:
            inicio_str, fin_str = horario.split('-')
            inicio_h, inicio_m = map(int, inicio_str.split(':'))
            fin_h, fin_m = map(int, fin_str.split(':'))
            duracion = (fin_h - inicio_h) * 60 + (fin_m - inicio_m)
            nuevos_horarios = []
            for desplazamiento in [30, 60, -30, -60]:
                nuevo_inicio_h = inicio_h + (desplazamiento // 60)
                nuevo_inicio_m = inicio_m + (desplazamiento % 60)
                if nuevo_inicio_m >= 60:
                    nuevo_inicio_m -= 60
                    nuevo_inicio_h += 1
                elif nuevo_inicio_m < 0:
                    nuevo_inicio_m += 60
                    nuevo_inicio_h -= 1
                if 8 <= nuevo_inicio_h <= 22 and 0 <= nuevo_inicio_m < 60:
                    nuevo_fin_h = nuevo_inicio_h + (duracion // 60)
                    nuevo_fin_m = nuevo_inicio_m + (duracion % 60)
                    if nuevo_fin_m >= 60:
                        nuevo_fin_m -= 60
                        nuevo_fin_h += 1
                    if nuevo_fin_h <= 23:
                        nuevo_horario = f"{nuevo_inicio_h:02d}:{nuevo_inicio_m:02d}-{nuevo_fin_h:02d}:{nuevo_fin_m:02d}"
                        nuevos_horarios.append((dia, nuevo_horario))
            if nuevos_horarios: alternativas.append(nuevos_horarios[0])
        return alternativas if len(alternativas) == len(patron_original) else None

    def detectar_solapamientos(self, asignaciones):
        solapamientos = []
        estructura_verificacion = self._inicializar_estructura_ocupacion_completa()
        for asignacion in asignaciones:
            materia = asignacion['materia']
            comision = asignacion['comision']
            sede = asignacion['sede']
            salon = asignacion['salon']
            if sede != 'PLATAFORMA VIRTUAL':
                for horario_str in asignacion['horarios_clases']:
                    if '(' in horario_str: horario_limpio = horario_str.split('(')[0].strip()
                    else: horario_limpio = horario_str
                    partes = horario_limpio.split(' ')
                    if len(partes) >= 2:
                        dia = partes[0]
                        rango_horario = ' '.join(partes[1:])
                        inicio_str, fin_str = rango_horario.split('-')
                        inicio_h, inicio_m = map(int, inicio_str.split(':'))
                        fin_h, fin_m = map(int, fin_str.split(':'))
                        hora_actual = inicio_h
                        minuto_actual = inicio_m
                        while hora_actual < fin_h or (hora_actual == fin_h and minuto_actual < fin_m):
                            slot_key = f"{hora_actual:02d}:{minuto_actual:02d}"
                            if estructura_verificacion[sede][salon][dia].get(slot_key) is not None:
                                materia_existente = estructura_verificacion[sede][salon][dia][slot_key]
                                solapamientos.append({
                                    'materia1': materia_existente.split('_')[0], 'comision1': int(materia_existente.split('_C')[1]),
                                    'materia2': materia, 'comision2': comision, 'dia': dia,
                                    'horario1': f"{inicio_str}-{fin_str}", 'horario2': rango_horario,
                                    'sede': sede, 'salon': salon, 'tipo': 'MISMO_SALON'
                                })
                                break
                            estructura_verificacion[sede][salon][dia][slot_key] = f"{materia}_C{comision}"
                            minuto_actual += 30
                            if minuto_actual >= 60:
                                minuto_actual = 0
                                hora_actual += 1
        return solapamientos

class OfertaAcademicaSistema:
    def __init__(self, df_historico, df_predicciones, sedes, carga_horaria, correlativas):
        self.df_historico = df_historico
        self.df_predicciones = df_predicciones
        self.sedes = sedes
        self.carga_horaria = carga_horaria
        self.correlativas = correlativas
        self.predicciones_originales = self._cargar_predicciones_reales()
        self.materias_disponibles = list(self.predicciones_originales.keys())
        self.sistema_prediccion = SistemaPrediccion(df_historico, df_predicciones)
        self.generador_horarios = GeneradorHorarios(sedes, carga_horaria)
        self.sistema_recomendaciones = SistemaRecomendacion(df_historico, correlativas)
        self.analizador_ia = AnalizadorTextoIA()
        self.chatbot = ChatbotOfertaAcademica(df_historico, df_predicciones)

    def _cargar_predicciones_reales(self):
        pred_dict = {}
        for _, row in self.df_predicciones.iterrows():
            pred_dict[row['MATERIA']] = row['pred_final']
        return pred_dict

    def _obtener_año_plan(self, materia):
        try:
            pred_materia = self.df_predicciones[self.df_predicciones['MATERIA'] == materia]
            if not pred_materia.empty and 'AÑO_PLAN' in pred_materia.columns:
                return int(pred_materia.iloc[0]['AÑO_PLAN'])
            historico_materia = self.df_historico[self.df_historico['MATERIA'] == materia]
            if not historico_materia.empty and 'AÑO_PLAN' in historico_materia.columns:
                return int(historico_materia.iloc[0]['AÑO_PLAN'])
            return 1
        except: return 1

    def calcular_comisiones(self, materia, es_virtual=False, capacidad_personalizada=None):
        alumnos_estimados = self.predicciones_originales.get(materia, 30)
        if capacidad_personalizada is not None: capacidad = capacidad_personalizada
        else: capacidad = 80 if es_virtual else 40
        comisiones = max(1, (alumnos_estimados + capacidad - 1) // capacidad)
        return comisiones, alumnos_estimados

    def predecir_demanda(self, materia):
        return self.sistema_prediccion.predecir_demanda(materia)

    def generar_oferta_academica(self, preferencias):
        try:
            salones_activos = preferencias.get('sedes_activas', [sede['nombre'] for sede in self.sedes])
            capacidad_presencial = preferencias.get('capacidad_presencial', 40)
            capacidad_virtual = preferencias.get('capacidad_virtual', 80)
            ratio_global = preferencias.get('ratio_global', 0)
            turnos_por_materia = preferencias.get('turnos_por_materia', {})
            materias_virtuales = preferencias.get('materias_virtuales', [])
            materias_a_procesar = [m for m in self.materias_disponibles if m not in preferencias.get('materias_excluidas', [])]
            todas_materias_info = []
            for materia in materias_a_procesar:
                año = self._obtener_año_plan(materia)
                alumnos_estimados = self.predecir_demanda(materia)
                horas_totales = self.carga_horaria.get(materia, 64)
                if materia in materias_virtuales:
                    modalidad = "Virtual"
                    comisiones, _ = self.calcular_comisiones(materia, True, capacidad_virtual)
                else:
                    modalidad = "Mixta"
                    comisiones, _ = self.calcular_comisiones(materia, False, capacidad_presencial)
                materia_info = {
                    'materia': materia, 'comisiones_totales': comisiones, 'alumnos_estimados': alumnos_estimados,
                    'carga_horaria': horas_totales, 'modalidad': modalidad, 'año_plan': año,
                    'capacidad_comision': capacidad_virtual if modalidad == "Virtual" else capacidad_presencial,
                    'turno_preferido': turnos_por_materia.get(materia, 'Noche')
                }
                todas_materias_info.append(materia_info)
            asignaciones_optimizadas = self.generador_horarios.optimizar_asignacion_horarios(
                todas_materias_info, salones_activos, ratio_global
            )
            solapamientos = self.generador_horarios.detectar_solapamientos(asignaciones_optimizadas)
            oferta_completa = self._reconstruir_oferta_con_asignaciones(todas_materias_info, asignaciones_optimizadas)
            oferta_completa['solapamientos'] = solapamientos
            recomendaciones = self.sistema_recomendaciones.generar_recomendaciones_optimizacion(oferta_completa)
            metricas = self._calcular_metricas_con_explicaciones(oferta_completa, todas_materias_info, salones_activos, capacidad_presencial)
            oferta_completa['resumen'].update(metricas)
            oferta_completa['recomendaciones'] = recomendaciones
            if st.session_state.get('usar_ia_generativa', False):
                with st.spinner("Generando insights con IA..."):
                    analisis_final = self.analizador_ia.analizar_patrones_demanda(self.df_historico, self.df_predicciones)
                    oferta_completa['analisis_ia_generativa'] = analisis_final
            return oferta_completa
        except Exception as e:
            st.error(f"Error generando oferta: {e}")
            return self._generar_oferta_basica(preferencias)

    def _reconstruir_oferta_con_asignaciones(self, materias_info, asignaciones):
        oferta_completa = {'oferta_por_año': {}}
        asignaciones_por_materia = {}
        for asignacion in asignaciones:
            materia = asignacion.get('materia', '')
            if materia not in asignaciones_por_materia: asignaciones_por_materia[materia] = []
            asignaciones_por_materia[materia].append(asignacion)
        for materia_info in materias_info:
            materia = materia_info['materia']
            año = materia_info['año_plan']
            if año not in oferta_completa['oferta_por_año']: oferta_completa['oferta_por_año'][año] = []
            asignaciones_materia = asignaciones_por_materia.get(materia, [])
            comisiones_presenciales = len([a for a in asignaciones_materia if a['sede'] != 'PLATAFORMA VIRTUAL'])
            comisiones_virtuales = len(asignaciones_materia) - comisiones_presenciales
            capacidad_total = materia_info['comisiones_totales'] * materia_info['capacidad_comision']
            utilizacion_materia = (materia_info['alumnos_estimados'] / capacidad_total * 100) if capacidad_total > 0 else 0
            oferta_completa['oferta_por_año'][año].append({
                'materia': materia, 'comisiones_totales': len(asignaciones_materia),
                'comisiones_presenciales': comisiones_presenciales, 'comisiones_virtuales': comisiones_virtuales,
                'alumnos_estimados': materia_info['alumnos_estimados'], 'carga_horaria': materia_info['carga_horaria'],
                'modalidad': materia_info['modalidad'], 'año_plan': año, 'capacidad_comision': materia_info['capacidad_comision'],
                'capacidad_total': capacidad_total, 'utilizacion_materia': utilizacion_materia,
                'correlativas_cursado': self.correlativas.get(materia, {}).get('Cursado', []),
                'correlativas_aprobado': self.correlativas.get(materia, {}).get('Aprobado', []),
                'detalle_comisiones': asignaciones_materia
            })
        total_materias = len(materias_info)
        total_comisiones = len(asignaciones)
        total_alumnos = sum(m['alumnos_estimados'] for m in materias_info)
        total_comisiones_presencial = sum(m['comisiones_presenciales'] for año_materias in oferta_completa['oferta_por_año'].values() for m in año_materias)
        total_comisiones_virtual = sum(m['comisiones_virtuales'] for año_materias in oferta_completa['oferta_por_año'].values() for m in año_materias)
        capacidad_total_sistema = sum(m['comisiones_totales'] * m['capacidad_comision'] for m in materias_info)
        utilizacion_sistema = (total_alumnos / capacidad_total_sistema * 100) if capacidad_total_sistema > 0 else 0
        oferta_completa['resumen'] = {
            'total_materias': total_materias, 'total_comisiones': total_comisiones,
            'total_comisiones_presencial': total_comisiones_presencial, 'total_comisiones_virtual': total_comisiones_virtual,
            'total_alumnos': total_alumnos, 'capacidad_total_sistema': capacidad_total_sistema,
            'utilizacion_sistema': utilizacion_sistema,
            'explicacion_metricas': self._generar_explicacion_metricas(total_materias, total_comisiones, total_alumnos, utilizacion_sistema)
        }
        return oferta_completa

    def _calcular_metricas_con_explicaciones(self, oferta, materias_info, salones_activos, capacidad_presencial):
        total_alumnos = sum(m['alumnos_estimados'] for m in materias_info)
        total_capacidad = sum(m['comisiones_totales'] * m['capacidad_comision'] for m in materias_info)
        utilizacion = (total_alumnos / total_capacidad * 100) if total_capacidad > 0 else 0
        capacidad_total_sedes = sum(len([s for s in salones_activos if s == sede['nombre']]) * sede['salones'] * capacidad_presencial for sede in self.sedes)
        return {
            'utilizacion_optimizada': utilizacion, 'capacidad_total_optimizada': total_capacidad,
            'capacidad_total_sedes': capacidad_total_sedes, 'sedes_utilizadas': len(salones_activos),
            'alumnos_por_comision_promedio': total_alumnos / len(materias_info) if materias_info else 0,
            'explicacion_utilizacion': f"Uso efectivo de recursos: {utilizacion:.1f}% de la capacidad total está siendo utilizada por estudiantes",
        }


    def _generar_explicacion_metricas(self, total_materias, total_comisiones, total_alumnos, utilizacion):
        return {
            'total_materias': f"Se están ofreciendo {total_materias} materias diferentes en el cuatrimestre",
            'total_comisiones': f"Se crearon {total_comisiones} comisiones en total para cubrir toda la demanda",
            'total_alumnos': f"Se espera atender a {total_alumnos} estudiantes en total",
            'utilizacion': f"El {utilizacion:.1f}% de la capacidad total está siendo utilizada, indicando buena eficiencia en el uso de recursos"
        }

    def _generar_oferta_basica(self, preferencias):
        return {
            'resumen': {
                'total_materias': len(self.materias_disponibles), 'total_comisiones': 0,
                'total_comisiones_presencial': 0, 'total_comisiones_virtual': 0,
                'total_alumnos': sum(self.predicciones_originales.values()), 'error': True
            },
            'oferta_por_año': {}, 'recomendaciones': [], 'solapamientos': []
        }

def mostrar_chatbot_oferta(sistema, oferta_actual):
    st.markdown('<div class="main-header">Asistente de Análisis de Oferta</div>', unsafe_allow_html=True)

    st.info("**Pregúntame sobre:** - Datos históricos de materias específicas - Predicciones actuales basadas en datos reales - Solapamientos de horarios - Capacidad y optimizaciones - Métricas específicas - Problemas detectados")

    if 'chat_historial' not in st.session_state:
        st.session_state.chat_historial = []

    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for mensaje in st.session_state.chat_historial:
        if mensaje['role'] == 'user':
            st.markdown(f'<div class="user-message"><strong>Tú:</strong> {mensaje["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="bot-message"><strong>Asistente:</strong> {mensaje["content"]}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    pregunta = st.text_input(
        "Escribe tu pregunta sobre la oferta académica:",
        value=st.session_state.get('pregunta_chat', ''),
        key="input_chat",
        placeholder="Ej: ¿Cuántos alumnos tuvo Álgebra en 2020-2C? ¿Cuáles son los datos reales?"
    )

    if st.button("Enviar pregunta", type="primary", use_container_width=True) and pregunta:
        with st.spinner("Buscando en datos reales..."):
            respuesta = sistema.chatbot.enviar_mensaje(pregunta, oferta_actual)

            st.session_state.chat_historial.append({"role": "user", "content": pregunta})
            st.session_state.chat_historial.append({"role": "assistant", "content": respuesta})

            st.session_state.pregunta_chat = ""
            st.rerun()

    if st.button("Limpiar conversación", use_container_width=True):
        st.session_state.chat_historial = []
        st.rerun()

def configurar_preferencias(sistema):
    st.markdown('<div class="main-header">Configurar Preferencias</div>', unsafe_allow_html=True)
    if 'preferencias' not in st.session_state:
        st.session_state.preferencias = {
            'sedes_activas': [sede['nombre'] for sede in sistema.sedes], 'materias_virtuales': [], 'materias_excluidas': [],
            'capacidad_presencial': 40, 'capacidad_virtual': 80, 'ratio_global': 0,
            'turnos_por_materia': {}
        }
    preferencias = st.session_state.preferencias
    st.markdown('<div class="secondary-header">Configuración de Sedes y Salones</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        sedes_activas = st.multiselect("Sedes activas para este cuatrimestre:", [sede['nombre'] for sede in sistema.sedes], default=preferencias.get('sedes_activas', [sede['nombre'] for sede in sistema.sedes]))
        preferencias['sedes_activas'] = sedes_activas
    with col2:
        st.write("**Salones disponibles por sede:**")
        for sede in sistema.sedes:
            if sede['nombre'] in sedes_activas:
                salones_disponibles = st.multiselect(f"Salones en {sede['nombre']}:", sede['salones_disponibles'], default=sede['salones_disponibles'], key=f"salones_{sede['nombre']}")
                sede['salones_disponibles'] = salones_disponibles
    st.markdown('<div class="secondary-header">Configuración de Capacidades</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        capacidad_presencial = st.number_input("Capacidad por comisión (Presencial):", min_value=10, max_value=100, value=preferencias.get('capacidad_presencial', 40), help="Número máximo de estudiantes por comisión presencial")
        preferencias['capacidad_presencial'] = capacidad_presencial
    with col2:
        capacidad_virtual = st.number_input("Capacidad por comisión (Virtual):", min_value=10, max_value=200, value=preferencias.get('capacidad_virtual', 80), help="Número máximo de estudiantes por comisión virtual")
        preferencias['capacidad_virtual'] = capacidad_virtual
    with col3:
        ratio_global = st.selectbox("Ratio virtual/presencial global:", [0, 2, 3, 4, 5], index=[0, 2, 3, 4, 5].index(preferencias.get('ratio_global', 0)) if preferencias.get('ratio_global', 0) in [0, 2, 3, 4, 5] else 0, help="Cada cuántas comisiones presenciales agregar una virtual (0 = solo presencial)")
        preferencias['ratio_global'] = ratio_global
    st.markdown('<div class="secondary-header">Preferencias Horarias por Materia</div>', unsafe_allow_html=True)
    st.write("**Configuración de turnos por materia:**")
    turnos_por_materia = preferencias.get('turnos_por_materia', {})
    materias_virtuales = preferencias.get('materias_virtuales', [])
    for materia in sistema.materias_disponibles:
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1: st.write(f"**{materia}**")
        with col2:
            turno_actual = turnos_por_materia.get(materia, 'Noche')
            turno_elegido = st.selectbox(f"Turno para {materia}", ["Mañana", "Tarde", "Noche"], index=["Mañana", "Tarde", "Noche"].index(turno_actual), key=f"turno_{materia}")
            turnos_por_materia[materia] = turno_elegido
        with col3:
            es_virtual = st.checkbox("100% Virtual", value=materia in materias_virtuales, key=f"virtual_{materia}", help="Marcar si la materia es completamente virtual")
            if es_virtual and materia not in materias_virtuales: materias_virtuales.append(materia)
            elif not es_virtual and materia in materias_virtuales: materias_virtuales.remove(materia)
    preferencias['turnos_por_materia'] = turnos_por_materia
    preferencias['materias_virtuales'] = materias_virtuales
    st.markdown('<div class="secondary-header">Excluir Materias</div>', unsafe_allow_html=True)
    materias_para_excluir = st.multiselect("Materias a excluir de la oferta académica:", sistema.materias_disponibles, default=preferencias.get('materias_excluidas', []))
    preferencias['materias_excluidas'] = materias_para_excluir
    st.checkbox("Usar IA Generativa para análisis avanzado", key="usar_ia_generativa", value=False, help="Activar para usar GPT-3.5-turbo a través de OpenRouter para análisis adicionales")
    if st.button("Guardar Configuración", type="primary", use_container_width=True):
        st.session_state.preferencias = preferencias
        st.success("Configuración guardada exitosamente")
    return preferencias

def mostrar_dashboard(sistema):
    st.markdown('<div class="main-header">Gráficos y primeras recomendaciones</div>', unsafe_allow_html=True)

    st.markdown("### Análisis de Distribución")
    grafico_seleccionado = st.radio("Selecciona el gráfico a visualizar:", ["Distribución de Alumnos por Año", "Top 10 Materias con Mayor Demanda"], horizontal=True)
    if grafico_seleccionado == "Distribución de Alumnos por Año":
        st.markdown("#### Distribución de Alumnos por Año")
        alumnos_por_año = {}
        for materia in sistema.materias_disponibles:
            año = sistema._obtener_año_plan(materia)
            alumnos = sistema.predicciones_originales.get(materia, 0)
            if año not in alumnos_por_año: alumnos_por_año[año] = 0
            alumnos_por_año[año] += alumnos
        if alumnos_por_año:
            fig = px.bar(x=list(alumnos_por_año.keys()), y=list(alumnos_por_año.values()), title="Alumnos por Año de Plan de Estudios", labels={'x': 'Año del Plan', 'y': 'Total de Alumnos Estimados'}, color_discrete_sequence=['#215086'])
            fig.update_layout(xaxis_title="Año del Plan de Estudios", yaxis_title="Cantidad de Alumnos", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            año_max = max(alumnos_por_año, key=alumnos_por_año.get)
            st.info(f"**Análisis:** El año {año_max} concentra la mayor cantidad de estudiantes ({alumnos_por_año[año_max]:,}), lo que requiere mayor oferta de materias de ese nivel.")
    else:
        st.markdown("#### Top 10 Materias con Mayor Demanda")
        top_materias = sorted(sistema.predicciones_originales.items(), key=lambda x: x[1], reverse=True)[:10]
        if top_materias:
            fig = px.bar(x=[m[1] for m in top_materias], y=[m[0] for m in top_materias], title="Top 10 Materias - Mayor Cantidad de Estudiantes Estimados", labels={'x': 'Estudiantes Estimados', 'y': 'Materia'}, orientation='h', color_discrete_sequence=['#215086'])
            fig.update_layout(yaxis={'categoryorder': 'total ascending'}, xaxis_title="Estudiantes Estimados", yaxis_title="Materias")
            st.plotly_chart(fig, use_container_width=True)
            materia_top, alumnos_top = top_materias[0]
            st.info(f"**Materia más demandada:** {materia_top} con {alumnos_top} estudiantes estimados")
    st.markdown("---")
    st.markdown("### Recomendaciones Iniciales del Sistema")

    total_alumnos = sum(sistema.predicciones_originales.values())
    capacidad_total = sum(sede['salones'] * 40 for sede in sistema.sedes)
    materias_alta_demanda = len([m for m, a in sistema.predicciones_originales.items() if a > 80])

    if total_alumnos > capacidad_total * 0.8:
        st.warning("**Alta Demanda Detectada:** La ocupación estimada supera el 80% de la capacidad física. **Recomendación:** Considerar aumentar capacidad virtual o habilitar sedes adicionales.")
    else:
        st.success("**Capacidad Adecuada:** La ocupación estimada está dentro de límites manejables. **Sugerencia:** Puedes optimizar la distribución entre sedes para mejorar eficiencia.")
    if materias_alta_demanda > len(sistema.materias_disponibles) * 0.3:
        st.warning("**Muchas Materias de Alta Demanda:** Más del 30% de las materias tienen alta demanda. **Recomendación:** Priorizar estas materias en la asignación de recursos y horarios.")

def mostrar_oferta_detallada(oferta):
    st.markdown('<div class="main-header">Oferta Académica Generada</div>', unsafe_allow_html=True)
    if oferta.get('resumen', {}).get('error', False):
        st.error("Se produjo un error al generar la oferta. Se muestra oferta básica.")
        return
    st.markdown('<div class="secondary-header">Resumen Ejecutivo</div>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    explicaciones = oferta['resumen'].get('explicacion_metricas', {})
    with col1:
        st.metric("Total Materias", oferta['resumen']['total_materias'], help=explicaciones.get('total_materias', ''))
        st.metric("Comisiones Presencial", oferta['resumen']['total_comisiones_presencial'], help="Número de comisiones que se dictan de forma presencial en sedes físicas")
    with col2:
        st.metric("Total Comisiones", oferta['resumen']['total_comisiones'], help=explicaciones.get('total_comisiones', ''))
        st.metric("Comisiones Virtual", oferta['resumen']['total_comisiones_virtual'], help="Número de comisiones que se dictan de forma virtual en plataforma online")
    with col3:
        st.metric("Total Alumnos", f"{oferta['resumen']['total_alumnos']:,}", help=explicaciones.get('total_alumnos', ''))
        st.metric("Sedes Utilizadas", oferta['resumen']['sedes_utilizadas'], help="Número de sedes físicas donde se están dictando clases presenciales")
    with col4:
        st.metric("Ocupación", f"{oferta['resumen']['utilizacion_sistema']:.1f}%", help=explicaciones.get('utilizacion', '') + f" (Capacidad total: {oferta['resumen']['capacidad_total_sistema']} estudiantes)")
    if 'solapamientos' in oferta and oferta['solapamientos']:
        st.markdown('<div class="secondary-header">Solapamientos de Horarios Detectados</div>', unsafe_allow_html=True)
        for solapamiento in oferta['solapamientos']:
            tipo_conflicto = "**CONFLICTO CRÍTICO - MISMO SALÓN**" if solapamiento.get('tipo') == 'MISMO_SALON' else "Conflicto de horarios"
            st.markdown(f'<div class="conflicto-grave"><strong>{tipo_conflicto}:</strong><br><strong>{solapamiento["materia1"]}</strong> (Comisión {solapamiento["comision1"]})<br><strong>{solapamiento["materia2"]}</strong> (Comisión {solapamiento["comision2"]})<br><strong>Sede:</strong> {solapamiento["sede"]} | <strong>Salón:</strong> {solapamiento["salon"]}<br><strong>Día:</strong> {solapamiento["dia"]} | <strong>Horario:</strong> {solapamiento["horario1"]} vs {solapamiento["horario2"]}</div>', unsafe_allow_html=True)
    else: st.success("No se detectaron solapamientos de horarios")
    if 'recomendaciones' in oferta and oferta['recomendaciones']:
        st.markdown('<div class="secondary-header">Recomendaciones Específicas</div>', unsafe_allow_html=True)
        for rec in oferta['recomendaciones']:
            mensaje_mejorado = rec['mensaje']
            if rec['prioridad'] == 'alta': st.error(f"**{rec['tipo']} - {rec['materia']}**: {mensaje_mejorado}")
            elif rec['prioridad'] == 'media': st.warning(f"**{rec['tipo']} - {rec['materia']}**: {mensaje_mejorado}")
            else: st.info(f"**{rec['tipo']} - {rec['materia']}**: {mensaje_mejorado}")
    if 'analisis_ia_generativa' in oferta:
        st.markdown('<div class="secondary-header">Análisis IA Generativa</div>', unsafe_allow_html=True)
        st.info(oferta['analisis_ia_generativa'])
    st.markdown('<div class="secondary-header">Oferta por Año - Detallada</div>', unsafe_allow_html=True)
    for año, materias_año in sorted(oferta['oferta_por_año'].items()):
        with st.expander(f"Año {año} - {len(materias_año)} materias - Ver detalles", expanded=True):
            for materia_info in materias_año:
                eficiencia_color = "🟢" if materia_info['utilizacion_materia'] > 70 else "🟡" if materia_info['utilizacion_materia'] > 50 else "🔴"
                with st.expander(f"{eficiencia_color} **{materia_info['materia']}** | {materia_info['modalidad']} | {materia_info['comisiones_totales']} comisiones | Utilización: {materia_info['utilizacion_materia']:.1f}%", expanded=False):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write(f"**Métricas de la Materia:**")
                        st.write(f"- **Alumnos estimados:** {materia_info['alumnos_estimados']}")
                        st.write(f"- **Carga horaria:** {materia_info['carga_horaria']} horas")
                        st.write(f"- **Comisiones presenciales:** {materia_info['comisiones_presenciales']}")
                        st.write(f"- **Comisiones virtuales:** {materia_info['comisiones_virtuales']}")
                        st.write(f"- **Capacidad total:** {materia_info['capacidad_total']} estudiantes")
                        st.write(f"- **Eficiencia de uso:** {materia_info['utilizacion_materia']:.1f}%")
                        if materia_info['correlativas_cursado']: st.write(f"**Correlativas de cursado:** {', '.join(materia_info['correlativas_cursado'])}")
                        if materia_info['correlativas_aprobado']: st.write(f"**Correlativas de aprobado:** {', '.join(materia_info['correlativas_aprobado'])}")
                    with col2:
                        st.write("**Horarios por comisión:**")
                        for comision in materia_info['detalle_comisiones']:
                            st.markdown(f'<div class="horario-box">', unsafe_allow_html=True)
                            st.write(f"**Comisión {comision['comision']}** - {comision['sede']}")
                            st.write(f"*Turno: {comision.get('turno', 'No especificado')}*")
                            for horario in comision['horarios_clases']: st.write(f"• {horario}")
                            st.markdown('</div>', unsafe_allow_html=True)
    def exportar_a_excel(oferta):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            resumen_data = [
                ['Total de Materias', oferta['resumen']['total_materias']],
                ['Total de Comisiones', oferta['resumen']['total_comisiones']],
                ['Comisiones Presenciales', oferta['resumen']['total_comisiones_presencial']],
                ['Comisiones Virtuales', oferta['resumen']['total_comisiones_virtual']],
                ['Total de Alumnos Estimados', oferta['resumen']['total_alumnos']],
                ['Ocupación del Sistema (%)', f"{oferta['resumen']['utilizacion_sistema']:.1f}%"],
                ['Sedes Utilizadas', oferta['resumen']['sedes_utilizadas']],
            ]
            df_resumen = pd.DataFrame(resumen_data)
            df_resumen.to_excel(writer, sheet_name='Resumen', index=False, header=False)
            oferta_data = []
            for año, materias in oferta['oferta_por_año'].items():
                for materia in materias:
                    for comision in materia['detalle_comisiones']:
                        horarios_comision = " | ".join(comision['horarios_clases'])
                        oferta_data.append({
                            'Año': año, 'Materia': materia['materia'], 'Comisión': comision['comision'],
                            'Modalidad': materia['modalidad'], 'Sede': comision['sede'], 'Salón': comision.get('salon', 'N/A'),
                            'Turno': comision.get('turno', 'N/A'), 'Horarios': horarios_comision,
                            'Alumnos Estimados': materia['alumnos_estimados'], 'Carga Horaria': materia['carga_horaria'],
                            'Utilización (%)': f"{materia['utilizacion_materia']:.1f}%"
                        })
            if oferta_data:
                df_oferta = pd.DataFrame(oferta_data)
                df_oferta.to_excel(writer, sheet_name='Oferta Detallada', index=False)
            if oferta.get('solapamientos'):
                solapamientos_data = []
                for solapamiento in oferta['solapamientos']:
                    solapamientos_data.append({
                        'Materia 1': solapamiento['materia1'], 'Comisión 1': solapamiento['comision1'],
                        'Materia 2': solapamiento['materia2'], 'Comisión 2': solapamiento['comision2'],
                        'Sede': solapamiento['sede'], 'Salón': solapamiento['salon'], 'Día': solapamiento['dia'],
                        'Horario 1': solapamiento['horario1'], 'Horario 2': solapamiento['horario2'],
                        'Tipo Conflicto': solapamiento.get('tipo', 'Desconocido')
                    })
                df_solapamientos = pd.DataFrame(solapamientos_data)
                df_solapamientos.to_excel(writer, sheet_name='Solapamientos', index=False)
        output.seek(0)
        return output
    excel_file = exportar_a_excel(oferta)
    st.download_button(label="Descargar Oferta Completa en Excel", data=excel_file, file_name=f"oferta_academica_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

def main():
    st.markdown('<div class="main-header">Oferta Académica Inteligente</div>', unsafe_allow_html=True)

    with st.spinner("Cargando datos del sistema..."):
        df_historico, df_predicciones = cargar_datos_reales()
        sistema = OfertaAcademicaSistema(df_historico, df_predicciones, sedes, carga_horaria, correlativas)

    with st.sidebar:
        st.markdown('<div class="sidebar-logo">', unsafe_allow_html=True)
        try:
            st.image("UNAB.png", use_container_width=True)
        except:
            st.info("**Universidad Nacional de Buenos Aires**")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("### Métricas del Sistema")

        total_materias = len(sistema.materias_disponibles)
        total_alumnos = sum(sistema.predicciones_originales.values())
        capacidad_total = sum(sede['salones'] * 40 for sede in sistema.sedes)
        utilizacion = (total_alumnos / capacidad_total) * 100 if capacidad_total > 0 else 0
        materias_alta_demanda = len([m for m, a in sistema.predicciones_originales.items() if a > 80])

        st.metric("Materias en Sistema", total_materias, help="Total de materias disponibles en el plan de estudios")
        st.metric("Alumnos Estimados", f"{total_alumnos:,}", help="Suma de todos los estudiantes estimados")
        st.metric("Ocupación Estimada", f"{utilizacion:.1f}%", help="Porcentaje de capacidad física utilizada")
        st.metric("Materias Alta Demanda", materias_alta_demanda, help="Materias con más de 80 estudiantes")

        st.markdown("---")
        st.markdown("### Generar Oferta")
        if st.button("Generar Oferta Optimizada", type="primary", use_container_width=True):
            with st.spinner("Generando oferta académica..."):
                oferta = sistema.generar_oferta_academica(st.session_state.preferencias)
                st.session_state.oferta_detallada = oferta
                st.success("Oferta generada")

    tab1, tab2, tab3, tab4 = st.tabs(["Inicio", "Configurar", "Generar Oferta", "Asistente"])

    with tab1:
        mostrar_dashboard(sistema)
    with tab2:
        configurar_preferencias(sistema)
    with tab3:
        st.markdown('<div class="main-header">Generar Oferta Académica</div>', unsafe_allow_html=True)

        if st.button("Generar Oferta Optimizada", type="primary", use_container_width=True, key="generar_oferta_main"):
            with st.spinner("Generando oferta académica..."):
                oferta = sistema.generar_oferta_academica(st.session_state.preferencias)
                st.session_state.oferta_detallada = oferta
                st.success("Oferta académica generada exitosamente")

        if 'oferta_detallada' in st.session_state:
            oferta = st.session_state.oferta_detallada
            mostrar_oferta_detallada(oferta)
        else:
            st.info("Haz clic en 'Generar Oferta Optimizada' para crear la oferta académica")

    with tab4:
        mostrar_chatbot_oferta(sistema, st.session_state.get('oferta_detallada', None))

if __name__ == "__main__":
    main()
