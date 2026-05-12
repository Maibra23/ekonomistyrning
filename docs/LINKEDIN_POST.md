# LinkedIn-inlagg

Att lasa om sjalvkostnadskalkyl, NPV och budgetering i boken ar en sak. Att faktiskt rakna med egna siffror och fa forklarat vad resultaten betyder, det ar nagot helt annat.

Darfor byggde jag Ekonomistyrning Sandbox, en interaktiv webbapp dar du:

- Gor sjalvkostnadskalkyl, bidragskalkyl och ABC-kalkyl med direkta resultat och waterfall-diagram
- Bedomer investeringar med NPV, IRR, payback, kanslighetsanalys och Monte Carlo-simulering (10 000 iterationer)
- Bygger resultat-, likviditets- och balansbudget som hangs ihop automatiskt
- Analyserar standardkostnadsavvikelser dekomponerade i volym, pris och effektivitet
- Testar dina kunskaper med LLM-genererade fragor dar numeriska svar verifieras mot kalkylatorn

En inbyggd LLM-tutor (Qwen3-8B via Hugging Face Inference Providers) forklarar varje resultat grundat i dina egna siffror, i ett register som blandar banktjanstemannens precision med akademisk rigorositet. Nar LLM inte ar tillganglig tar deterministiska mallar over, sa appen alltid fungerar.

Teknik: Python 3.11, Streamlit, Plotly, Qwen3-8B, huggingface-hub, numpy, pandas, scipy.

Baserat pa Goran Anderssons "Ekonomistyrning: beslut och handling" (Studentlitteratur).

Testa sjalv (lank i kommentarerna) och hor garna av dig med feedback.

#ekonomistyrning #studentliv #python #datavisualisering #fintech #riskanalys #llm #qwen3
