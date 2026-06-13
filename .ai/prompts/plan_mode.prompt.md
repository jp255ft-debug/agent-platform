# PLAN MODE Prompt — Planejamento Estruturado

## 🎯 Instruções Obrigatórias

### 1. Chain of Thought
Antes de propor um plano, analise:
1. **Contexto**: Qual é o problema a ser resolvido?
2. **Restrições**: Quais são as limitações técnicas/arquiteturais?
3. **Trade-offs**: Quais são as opções e seus prós/contras?
4. **Decisão**: Qual caminho escolher e por quê?

### 2. Referência aos ADRs
- Consulte os ADRs em `docs/adr/` para decisões já tomadas
- Se uma nova decisão arquitetural for necessária, proponha um novo ADR
- Nunca contradiga um ADR existente sem justificativa explícita

### 3. Estrutura do Plano
Todo plano deve conter:
- **Objetivo**: O que será feito
- **Arquivos afetados**: Lista completa
- **Dependências**: O que precisa existir primeiro
- **Passos**: Sequência de implementação
- **Riscos**: O que pode dar errado
- **Testes**: Como validar

### 4. Referências
Consulte estes arquivos para contexto:
- `.ai/CLAUDE.md` — Decisões arquiteturais
- `.ai/knowledge-base/architecture_patterns.md` — Padrões
- `docs/adr/` — ADRs existentes
- `docs/domain-models/` — Modelos de domínio

---

## 📋 Template de Plano

```markdown
## 🎯 Objetivo
[Descrição clara do que será implementado]

## 📁 Arquivos Afetados
| Arquivo | Ação | Motivo |
|---------|------|--------|
| path/file.py | Criar/Modificar | ... |
| path/file.sol | Criar | ... |

## 🔗 Dependências
- [ ] Dependência 1 (ex: contrato X precisa existir)
- [ ] Dependência 2 (ex: migration Y precisa rodar)

## 📋 Passos
1. [Passo 1] — [detalhes]
2. [Passo 2] — [detalhes]
3. [Passo 3] — [detalhes]

## ⚠️ Riscos
- [Risco 1] — [mitigação]
- [Risco 2] — [mitigação]

## 🧪 Testes
- [Teste 1]
- [Teste 2]

## 📚 Referências
- ADR-00X: [link]
- `docs/domain-models/`: [link]
```
