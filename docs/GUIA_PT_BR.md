# Como manter este software

Este projeto tem pasta e repositório próprios, sem dependência do site acadêmico ou do artigo. Os próximos softwares devem seguir o mesmo padrão, cada um em seu repositório.

## Estado de 25 de novembro de 2026

139 testes computacionais aprovados, incluindo 54 combinações de estados da adaptação. O motor original e a configuração sintética somam 13 arquivos preservados e verificados por SHA256. Estes números não representam validação científica.

A edição de navegador é um protótipo em Python/Pyodide com NumPy. O ambiente de conferência visual não iniciou nesta sessão; a equivalência dentro do navegador, a navegação, os downloads e os controles ainda precisam ser conferidos. Por isso esta preparação não habilita publicação automática nem anuncia uma ferramenta pública validada.

## Rotina

1. Abrir esta pasta no Codex e descrever a alteração.
2. Trabalhar em branch, mantendo o motor e as configurações originais preservados.
3. Executar testes e build, conferir a prévia e registrar a mudança.
4. Publicar somente a versão revisada. Uma release citada no artigo permanece identificável mesmo com novas versões.

Executar localmente com .venv/Scripts/python.exe. As instruções completas estão no README. dist é uma saída gerada e não deve receber edição manual. app mantém o servidor Python original; web contém a adaptação do transporte para o navegador; engine mantém a lógica científica.

O repositório começa privado. O envio ao GitHub não significa habilitação do GitHub Pages, depósito com DOI ou registro de software. Autoria, titularidade e licença permanecem registradas como pendentes, sem atribuição automática.
