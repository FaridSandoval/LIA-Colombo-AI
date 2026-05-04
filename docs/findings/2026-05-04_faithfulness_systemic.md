# Hallazgo Técnico: Faithfulness sistémico en 0 por respuestas "de memoria"
**Fecha:** 4 de mayo de 2026
**Categoría:** Evaluación RAG (Métricas RAGAS)

## Síntoma
Durante el benchmark comparativo de modelos (`gemma2:9b`, `llama3.1:8b`, `qwen2.5:7b`) sobre el golden set de GRAMMAR (25 ítems), se observó una caída severa en la métrica de *faithfulness* (fidelidad al texto), llegando a 0.0 en varios casos, acompañado de `context_precision` y `context_recall` en 0.0.

## Diagnóstico
El sistema de recuperación (Retrieval) no está logrando extraer los fragmentos correctos del corpus (Murphy's Grammar) para responder las consultas. Ante la falta de contexto útil, los modelos LLM (especialmente Llama 3.1 y Gemma 2) optan por utilizar su conocimiento paramétrico ("de memoria") para ayudar al usuario de forma pedagógica.

Dado que la respuesta generada es correcta pero **no proviene del corpus inyectado**, el juez RAGAS asigna un puntaje de `faithfulness = 0`. El sistema lo detecta correctamente: el filtro de `low_confidence` se activa en el 96% de los casos (24/25).

## Decisión de Diseño Pendiente (Para discutir con Tutor)
Actualmente, el sistema prioriza la **utilidad pedagógica** (responder aunque sea de memoria si sabe la respuesta) sacrificando la **trazabilidad académica** (citar el corpus). 

**Pregunta para asesoría:** 
¿Deberíamos configurar los *guardrails* para que LIA se rehúse estrictamente a responder si no encuentra la información en el corpus institucional, o mantenemos la flexibilidad actual asumiendo métricas bajas de RAGAS?