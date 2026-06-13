# ACT MODE Prompt — Geração de Código com Grounding

## 🎯 Instruções Obrigatórias

### 1. Grounding Factual
- **Cite o arquivo/função** que você está modificando ou referenciando
- **Não invente APIs** que não existem no código
- Se não tiver certeza, diga "não sei" em vez de alucinar

### 2. Chain of Thought
Antes de escrever código, explique:
1. Qual é o objetivo desta implementação
2. Quais arquivos serão afetados
3. Qual é o fluxo de dados
4. Quais são os edge cases

### 3. Verificações Obrigatórias
- ✅ O código é sintaticamente válido?
- ✅ Os imports existem no projeto?
- ✅ Os type hints estão corretos?
- ✅ Os padrões do projeto foram seguidos?
- ✅ Testes foram considerados?

### 4. Referências
Consulte estes arquivos para contexto:
- `.ai/AGENTS.md` — Convenções de código
- `.ai/knowledge-base/architecture_patterns.md` — Padrões arquiteturais
- `.ai/knowledge-base/solidity_patterns.md` — Padrões Solidity
- `.ai/knowledge-base/api_conventions.md` — Convenções de API

---

## 📋 Template de Resposta

```markdown
## Análise
[Explicar o que precisa ser feito]

## Arquivos Afetados
- `caminho/do/arquivo1.py` — [motivo]
- `caminho/do/arquivo2.sol` — [motivo]

## Implementação
[Código com citações das fontes]

## Edge Cases Considerados
- [Caso 1]
- [Caso 2]

## Validação
- [ ] Sintaxe verificada
- [ ] Imports existentes
- [ ] Type hints corretos
- [ ] Padrões seguidos
```
