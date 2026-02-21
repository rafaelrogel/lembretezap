# Zapista Roadmap: Futuras Melhorias 🚀

Este documento registra ideias e otimizações planejadas para melhorar a performance, custo e experiência do usuário no Zapista.

## ⚡ Performance & Latência
- [ ] **Integração com Groq**: Configurar o Groq como provedor para o modelo de "Scope" (triagem, resumos, detecção de sentimentos). O Groq oferece latência ultra-baixa (< 1s) e custo reduzido (Llama 3 8B).
- [ ] **Otimização de Prompts**: Condensar os arquivos de sistema (`AGENTS.md`, `SOUL.md`) para reduzir o tempo de processamento inicial do LLM.
- [ ] **Modo Produção (Clean Logs)**: Desativar logs de debug intensivos (`debug.log`) e auditoria excessiva em tempo real para aliviar o I/O da VPS.
- [ ] **Cache de Contexto**: Implementar cache para partes estáticas do system prompt.

## 💰 Otimização de Custo
- [ ] **Migração Total para Mimo/Groq**: Avaliar se tarefas complexas do DeepSeek podem ser movidas para modelos menores e mais baratos sem perda de qualidade.
- [ ] **Compressão de Sessão Agressiva**: Reduzir o número de mensagens mantidas em memória viva para economizar tokens.

## 🌍 Localização & UX
- [ ] **Suporte a Novas Línguas**: Expandir os aliases e handlers nativos para Francês e Alemão.
- [ ] **Feedback em Áudio Inteligente**: Otimizar o tempo de síntese de voz (TTS) usando modelos mais leves na VPS.

---
*Atualizado em: 2026-02-21*
