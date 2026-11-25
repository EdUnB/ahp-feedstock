# Como manter este software

Este projeto tem pasta e repositório próprios, sem dependência do site acadêmico ou do artigo. Os próximos softwares devem seguir o mesmo padrão, cada um em seu repositório.

## Estado de 25 de novembro de 2026

139 testes computacionais aprovados, incluindo 54 combinações de estados da adaptação. O motor original e a configuração sintética somam 13 arquivos preservados e verificados por SHA256. Estes números não representam validação científica.

A edição de navegador foi testada no Chrome em sessão isolada: 54 combinações comparadas ao motor Python, baseline, pesos extremos, restauração, exportações JSON/CSV, entradas inválidas e largura móvel de 390 px. Os cálculos foram executados no navegador, sem requisições a uma API remota de cálculo. Essas verificações não representam validação científica. A publicação no GitHub Pages foi solicitada pelo titular; o deploy foi concluído e a auditoria completa passou também no endereço público: https://edunb.github.io/ahp-feedstock/.

## Rotina

1. Abrir esta pasta no Codex e descrever a alteração.
2. Trabalhar em branch, mantendo o motor e as configurações originais preservados.
3. Executar testes e build, conferir a prévia e registrar a mudança.
4. Publicar somente a versão revisada. Uma release citada no artigo permanece identificável mesmo com novas versões.

Executar localmente com .venv/Scripts/python.exe. As instruções completas estão no README. dist é uma saída gerada e não deve receber edição manual. app mantém o servidor Python original; web contém a adaptação do transporte para o navegador; engine mantém a lógica científica.

O repositório foi inicialmente preparado em modo privado. A visibilidade pode passar a pública para viabilizar o GitHub Pages no plano gratuito, conforme a publicação solicitada. O envio ao GitHub não significa habilitação do GitHub Pages, depósito com DOI ou registro de software. Autoria, titularidade e licença permanecem registradas como pendentes, sem atribuição automática.

## Abrir e testar

Acesse https://edunb.github.io/ahp-feedstock/ e aguarde o indicador Motor Python no navegador. Use Exemplo sintético, marque a confirmação de análise exploratória e execute o AHP. Depois ative a análise dos pesos na etapa 05. A primeira abertura precisa carregar Python e NumPy pela internet. Não é necessário instalar Python no computador do visitante.
