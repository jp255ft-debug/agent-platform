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

### 🔍 Diagnóstico Obrigatório Antes de Modificar Código

Quando um teste falha com erro genérico (ex: `AssertionError`, `Expected X to be Y`):

1. **Diagnostique a causa raiz** antes de modificar qualquer código de negócio:
   ```python
   # Adicione prints estratégicos NO TESTE ou NO CÓDIGO para entender o estado real
   print(f"[DEBUG] response.status_code={response.status_code}")
   print(f"[DEBUG] response.json()={response.json()}")
   print(f"[DEBUG] mock_db.execute.call_args={mock_db.execute.call_args}")
   ```
2. **Execute o teste novamente** apenas para ler os logs de diagnóstico (não para "passar").
3. **Analise o output** para identificar onde está a divergência entre o esperado e o real.
4. **Remova os prints de diagnóstico** e só então faça a correção necessária.

**Regra:** Nunca altere a lógica de negócio ou mocks sem antes ter evidência empírica do estado real do sistema via logs/prints.

### 💾 Checkpoint Automático (Git Safety Net)

Antes de refatorar agregados do Event Store, alterar lógica de persistência, ou modificar handlers de domínio:

1. **Crie um checkpoint automático:**
   ```bash
   git add -A && git commit -m "WIP: pre-refactoring checkpoint - {descrição breve}"
   ```
2. **Execute as alterações e testes.**
3. **Se o Circuit Breaker for acionado** (mais de 3 falhas consecutivas):
   - Execute `git reset --hard HEAD~1` para reverter TODAS as alterações da tentativa
   - Isso garante que o estado do projeto volta exatamente ao que era antes

**ATENÇÃO:** Não use o checkpoint como desculpa para fazer alterações de baixa qualidade — o propósito é permitir rollback limpo, não incentivar tentativa-e-erro.

### ⛔ Regra de Falha Crítica (Circuit Breaker)
Se você executar `pytest` ou `forge test` e **o mesmo teste falhar mais de 3 vezes consecutivas**:

1. **PARE IMEDIATAMENTE.** Não tente "adivinhar" a solução alterando mocks aleatoriamente.
2. **Execute `git diff`** para listar todas as mudanças feitas até agora.
3. **Restaure os arquivos modificados** ao estado original com `git checkout -- <arquivo>` para cada arquivo alterado.
4. **Explique no log** quais foram as 3 tentativas, o que cada uma alterou, e qual a possível causa raiz.
5. **Solicite intervenção humana** com um resumo claro do problema, ou **peça para retornar ao PLAN MODE** para replanejar a abordagem.

**Exceção:** Alterações em fixtures de teste (`tests/conftest.py`, `tests/integration/conftest.py`) são PROIBIDAS durante tentativas de correção — estas só podem ser alteradas com autorização explícita do usuário.

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
