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

### 3. Verificações Obrigatórias (Antes de Escrever)
- ✅ O código é sintaticamente válido?
- ✅ Os imports existem no projeto?
- ✅ Os type hints estão corretos?
- ✅ Os padrões do projeto foram seguidos?
- ✅ Testes foram considerados?

### 4. Verificação Automática (Após Escrever)
**IMPORTANTE**: Após cada alteração significativa, você DEVE executar a verificação apropriada:

#### Para Python:
```bash
python .ai/validation/validate_python.py --path backend/app/
pytest backend/tests/unit/test_<arquivo_alterado>.py -v
```

#### Para Solidity:
```bash
python .ai/validation/validate_solidity.py --path contracts/src/
forge test --match-path contracts/test/<arquivo_alterado>.t.sol -vvv
```

#### Para TypeScript:
```bash
cd node-service && npx tsc --noEmit
cd node-service && npm test -- --testPathPattern=<arquivo_alterado>
```

**Só considere a tarefa concluída quando TODAS as verificações passarem.**

### 5. Referências
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
- [ ] `validate_python.py` executado sem erros
- [ ] Testes relevantes passando
```
