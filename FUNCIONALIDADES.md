# Funcionalidades do MeuFinanças

## 1. Visão geral

O **MeuFinanças** é um aplicativo Android de controle financeiro pessoal. Ele permite registrar receitas e despesas, acompanhar saldo e consumo mensal, organizar lançamentos por categoria, controlar cartões de crédito, definir metas de gastos, agendar valores futuros e importar dados bancários por Open Finance através da Pluggy.

O sistema é formado por três partes:

- **Aplicativo Android:** interface nativa escrita em Kotlin com Jetpack Compose.
- **API:** backend em Python com FastAPI, responsável pelas regras de negócio e pela comunicação com o banco de dados e a Pluggy.
- **Persistência:** Supabase/PostgreSQL, onde ficam usuários, categorias, transações, cartões, metas, conexões Open Finance, contas importadas e o histórico idempotente de webhooks.

Os valores monetários são armazenados como números inteiros em centavos. Assim, `1000` representa `R$ 10,00`, evitando erros de arredondamento com números decimais.

---

## 2. Navegação do aplicativo

A tela inicial é o **Dashboard**. A partir dele, o usuário acessa:

| Tela | Finalidade |
|---|---|
| Dashboard | Visão consolidada da situação financeira e dos indicadores do mês. |
| Transações | Consulta, busca, filtro, criação, edição e efetivação de lançamentos. |
| Categorias | Gerenciamento das categorias de receitas e despesas. |
| Cartões de Crédito | Cadastro manual e acompanhamento de limites e faturas. |
| Metas de Gastos | Definição de limites mensais para grupos de categorias. |
| Open Finance | Conexão de instituições financeiras e sincronização dos dados da Pluggy. |

O acesso às transações também pode partir de um cartão exibido no Dashboard. Nesse caso, a tela de transações já abre filtrada pelo cartão escolhido.

---

## 3. Dashboard financeiro

O Dashboard apresenta uma visão mensal e consolidada das finanças. O mês pode ser alterado pelos botões de mês anterior e próximo mês. Ao trocar o período, o aplicativo recarrega em paralelo o resumo, as transações e a evolução mensal; respostas antigas são ignoradas quando o usuário muda de mês antes de uma requisição terminar.

### 3.1. Atalhos

No topo existem atalhos para:

- conectar e gerenciar instituições no Open Finance;
- abrir o gerenciamento de cartões;
- abrir as metas de gastos;
- abrir a configuração de categorias;
- adicionar uma nova transação pelo botão flutuante.

### 3.2. Cartões no Dashboard

Quando existem cartões cadastrados ou importados, o Dashboard mostra uma faixa horizontal de cartões. Cada cartão apresenta o nome e o limite disponível. Tocar em um cartão abre a relação de transações já filtrada por ele.

### 3.3. Indicadores do mês

O resumo exibe:

- **Saldo disponível:** saldo acumulado de receitas realizadas menos despesas realizadas em dinheiro até o final do mês selecionado.
- **Receitas:** entradas realizadas no mês.
- **Despesas:** saídas realizadas em dinheiro no mês.
- **Dinheiro e cartão:** detalhamento das despesas por forma de pagamento.
- **Provisões a receber:** receitas futuras ou pendentes registradas como provisão.
- **Provisões a pagar:** despesas futuras ou pendentes registradas como provisão.
- **Previsão de saldo final:** projeção que considera o saldo e os valores provisionados.

Para o mês corrente, se houver contas bancárias importadas pela Pluggy, o saldo disponível usa a soma dos saldos informados pelas instituições. Isso evita depender apenas do histórico importado, que pode possuir uma janela limitada. Para outros meses, o saldo é calculado pelo histórico salvo.

Compras no cartão entram no consumo e nos indicadores do cartão, mas não reduzem diretamente o saldo em dinheiro. O pagamento da fatura é tratado como movimento de caixa e não é contado novamente na distribuição por categoria, evitando duplicar o consumo.

### 3.4. Planejamento do próximo mês

O painel “Planejamento Próximo Mês” mostra:

- provisões a pagar sem vínculo com cartão;
- faturas previstas dos cartões;
- outras despesas já realizadas/agendadas para o próximo mês;
- total previsto de saídas.

A previsão de faturas usa a data de fechamento e de vencimento de cada cartão. Quando já existe uma provisão de fatura, o valor provisionado é usado; caso contrário, o sistema soma as compras e desconta créditos ou estornos do ciclo correspondente.

### 3.5. Evolução mensal

O Dashboard contém um gráfico de evolução financeira com receitas, despesas e saldo ao longo dos meses. O backend entrega uma janela de sete meses, composta pelo mês selecionado, pelos três anteriores e pelos três seguintes, e inclui separadamente o consumo em cartão.

### 3.6. Metas no Dashboard

As metas cadastradas para o mês aparecem com:

- nome da meta;
- valor gasto;
- valor limite;
- percentual consumido.

O atalho “Ver mais” abre a tela completa de metas.

### 3.7. Provisões pendentes

O Dashboard lista as contas a pagar e a receber marcadas como provisão. Cada item mostra descrição, vencimento e valor. O botão de confirmação transforma a provisão em transação realizada sem criar um lançamento duplicado.

### 3.8. Análises por categoria

O painel oferece duas leituras dos gastos:

- **Distribuição de Despesas:** composição percentual e monetária do consumo por categoria, incluindo gastos em dinheiro e compras no cartão.
- **Maiores Gastos:** ranking das categorias com maior valor consumido no mês.

Pagamentos de fatura são excluídos dessa análise, pois as compras que formaram a fatura já foram contabilizadas nas respectivas categorias.

---

## 4. Transações

### 4.1. Consulta e filtros

A tela de transações permite:

- navegar entre meses;
- listar os lançamentos do período;
- buscar pelo texto da descrição;
- filtrar por categoria através de chips;
- filtrar por cartão;
- limpar o filtro de cartão;
- recarregar os dados após um erro.

A busca possui atraso de 300 ms após a digitação. Isso reduz requisições enquanto o usuário ainda está escrevendo e cancela resultados de pesquisas anteriores.

Cada lançamento mostra seu valor com sinal de entrada ou saída, a descrição, a categoria, a data e informações visuais relacionadas ao tipo e à provisão. Tocar no item abre a edição.

### 4.2. Cadastro de receitas e despesas

O formulário de transação permite informar:

- tipo: receita ou despesa;
- valor em reais;
- categoria compatível com o tipo escolhido;
- descrição opcional;
- data da transação;
- indicação de provisão;
- forma de pagamento para despesas: dinheiro ou cartão;
- cartão utilizado, quando aplicável;
- número de parcelas para compras no cartão;
- repetição mensal por um período para despesas fixas em dinheiro.

O valor digitado é formatado como moeda brasileira e convertido para centavos antes do envio.

Uma categoria pode ser criada dentro do próprio formulário. Depois da criação, a lista é atualizada e a nova categoria pode ser usada imediatamente.

### 4.3. Provisões

Uma transação marcada como provisão representa um valor previsto, ainda não realizado. Ela pode ser uma conta a pagar ou uma receita a receber. A opção de efetivar atualiza o mesmo registro e remove a marca de provisão.

Provisões não entram nos totais realizados de receita, despesa ou saldo até serem efetivadas.

### 4.4. Despesas fixas

Para despesas em dinheiro criadas manualmente, a interface oferece “Despesa Fixa” e as opções “Todo mês” ou “Por um período”. Quando um número de meses maior que um é enviado, o backend cria um lançamento para cada mês:

- o primeiro preserva a situação de provisão escolhida pelo usuário;
- os meses futuros são criados como provisões;
- a descrição recebe a posição, como `(Fixo 1/6)`;
- a data avança mês a mês, ajustando automaticamente dias inexistentes no calendário.

**Comportamento atual relevante:** a opção visual “Todo mês” não possui um agendador contínuo no backend. Sem um número de meses, ela cria somente o lançamento inicial. A repetição efetiva está implementada para a opção “Por um período”.

### 4.5. Compras parceladas

Parcelamento é permitido apenas para despesas pagas com cartão. Ao salvar uma compra parcelada:

- o valor total é dividido pelo número de parcelas;
- eventual resto em centavos é acrescentado à primeira parcela;
- cada parcela é criada em um mês consecutivo;
- a descrição recebe a numeração, como `(1/10)`;
- cada parcela é associada ao período de fatura calculado a partir do dia de fechamento do cartão.

Despesas em dinheiro são obrigatoriamente à vista.

### 4.6. Edição e exclusão

Transações podem ter valor, tipo, categoria, descrição, data, provisão, forma de pagamento e cartão alterados. Uma edição recalcula o período da fatura quando necessário.

Transações manuais podem ser excluídas pelo formulário de edição. Para transações importadas da Pluggy, o botão de exclusão não é oferecido. Edições feitas pelo usuário em lançamentos importados são marcadas no banco; sincronizações futuras preservam a descrição e a categoria escolhidas pelo usuário.

---

## 5. Categorias

As categorias organizam receitas e despesas e alimentam os filtros, gráficos, rankings e metas.

A tela separa as categorias em duas abas:

- despesas;
- receitas.

O usuário pode criar uma categoria com nome e emoji. Categorias personalizadas podem ser renomeadas, ter o ícone alterado e ser excluídas.

O sistema cria automaticamente categorias padrão para cada usuário novo. Entre as despesas estão Alimentação, Transporte, Moradia, Saúde, Lazer, Educação, Vestuário, Supermercado, Farmácia e Outros. Entre as receitas estão Salário, Freelance, Investimentos, Presentes e Outros.

Categorias padrão ficam bloqueadas para edição e exclusão. Não é permitido ter duas categorias com o mesmo nome para o mesmo usuário. Ao excluir uma categoria personalizada, todas as transações ligadas a ela são migradas para a categoria padrão “Outros” do mesmo tipo. Se essa categoria de segurança não existir, o backend a recria antes da migração.

---

## 6. Cartões de crédito

### 6.1. Cadastro manual

O usuário pode cadastrar um cartão informando:

- nome;
- limite total;
- dia de fechamento;
- dia de vencimento.

Os dias devem estar entre 1 e 31 e o limite deve ser maior que zero. Cartões manuais podem ser editados ou excluídos.

### 6.2. Resumo do cartão

Para cada cartão, o aplicativo mostra:

- limite total;
- valor da fatura corrente;
- limite disponível;
- dia de fechamento;
- dia de vencimento;
- origem manual ou Open Finance.

Para cartões manuais, a fatura corrente considera as compras entre o fechamento anterior e o fechamento atual, somando débitos e abatendo créditos/estornos. O limite disponível corresponde ao limite total menos a fatura corrente.

Para cartões importados, o sistema usa os limites e dados fornecidos pela instituição quando disponíveis.

### 6.3. Período de fatura

Compras feitas até o fechamento pertencem à fatura do mês. Compras posteriores pertencem à fatura seguinte. Quando o dia configurado não existe em determinado mês, é usado o último dia daquele mês.

Depois do fechamento de um cartão manual, o backend pode criar automaticamente uma provisão de pagamento da fatura, com vencimento no dia configurado. A provisão é gerada apenas quando existe consumo, evita duplicidade e usa a categoria de despesa “Outros”. Cartões vindos da Pluggy não recebem essa provisão sintética, pois a instituição já fornece sua movimentação.

A tela também possui o botão “Conectar banco”, que leva ao Open Finance.

---

## 7. Metas de gastos

As metas estabelecem um teto mensal para um grupo de categorias de despesa.

O usuário pode:

- navegar entre os meses;
- criar uma meta com nome e valor limite;
- selecionar uma ou várias categorias de despesa para a mesma meta;
- editar uma meta existente;
- excluir uma meta;
- acompanhar valor gasto, valor restante e percentual consumido.

É obrigatório selecionar pelo menos uma categoria. Uma meta com o mesmo nome, mês e usuário é atualizada em vez de duplicada. O progresso soma o consumo de todas as categorias selecionadas. O valor restante pode ficar negativo quando a meta é ultrapassada, e o percentual pode superar 100%.

---

## 8. Open Finance com Pluggy

### 8.1. Conexão de instituições

O usuário inicia o fluxo em “Conectar instituição”. O aplicativo solicita ao backend um Connect Token e abre o Pluggy Connect dentro de uma WebView. As credenciais privadas da Pluggy permanecem somente no servidor.

Após a autorização:

1. o widget devolve o `itemId` da conexão;
2. o aplicativo registra esse item no backend;
3. o backend associa a conexão ao usuário;
4. a importação das contas, cartões e transações é executada em segundo plano;
5. os dados ficam disponíveis no restante do aplicativo.

O modo sandbox pode ser habilitado por variável de ambiente para testes. O widget trata sucesso, erro e fechamento através de uma ponte JavaScript controlada pelo app.

### 8.2. Lista e estado das conexões

Cada conexão exibe:

- instituição e imagem do conector;
- situação da conexão e da última execução;
- nomes e quantidade de contas/cartões encontrados;
- data da última importação bem-sucedida;
- horário da última sincronização salva;
- próxima sincronização automática informada pela Pluggy;
- último erro, quando houver.

Se o acesso bancário precisar de atenção, “Corrigir acesso” reabre o widget para atualizar a conexão existente. O erro `ITEM_USER_ALREADY_EXISTS` é convertido em uma orientação para reutilizar ou atualizar a conexão já cadastrada.

### 8.3. Atualização manual

“Atualizar dados agora” coloca todas as conexões do usuário na fila de importação. Essa ação consulta os dados que já estão disponíveis na Pluggy; ela não obriga o banco a iniciar uma nova coleta.

Como a API responde antes do fim da importação, o Android consulta o estado a cada dois segundos, por até um minuto. Ele informa quando todas as conexões foram atualizadas, quando uma delas apresentou erro ou quando a conclusão ainda não pôde ser confirmada.

Uma falha em uma instituição não impede a tentativa nas demais conexões.

### 8.4. Importação de contas, cartões e transações

Uma conexão pode fornecer várias contas e cartões. O backend:

- mantém uma representação das contas financeiras e de seus saldos;
- cria ou atualiza cartões de origem Pluggy;
- percorre todas as contas da conexão e importa suas transações;
- processa lotes de transações para reduzir o número de operações no banco;
- deduplica lançamentos pelo `pluggy_transaction_id`;
- identifica entrada e saída pelo tipo informado pela Pluggy;
- associa categorias importadas às categorias locais, com fallback para “Outros”;
- usa nome do estabelecimento ou descrição como texto do lançamento;
- relaciona compras de crédito ao cartão e ao período da fatura;
- ignora o lado duplicado do pagamento da fatura dentro da conta de cartão;
- preserva categoria e descrição de uma transação importada que já foi editada pelo usuário.

### 8.5. Webhooks

O backend recebe eventos da Pluggy em `/webhooks/pluggy`. A URL precisa ser HTTPS pública e inclui um segredo configurado no servidor. Os eventos são registrados com identificador único, payload, situação de processamento, erro e datas de recebimento/processamento.

Esse registro torna o processamento idempotente: novas tentativas do mesmo webhook não devem duplicar seus efeitos. Os eventos atualizam conexões e disparam reconciliação dos dados quando necessário.

### 8.6. Desconexão

Ao desconectar uma instituição, o aplicativo pede confirmação e avisa que os dados importados serão removidos. A operação exclui:

- transações importadas daquela conexão;
- cartões importados daquela conexão;
- contas financeiras importadas;
- registro da conexão.

Dados cadastrados manualmente e dados de outras instituições permanecem intactos.

---

## 9. Lembretes e notificações

O aplicativo solicita permissão de notificações no Android 13 ou superior. Um trabalho periódico do WorkManager é agendado a cada 12 horas com o nome único `unpaid_bills_reminder`.

O trabalho consulta o mês atual e o anterior, procura despesas marcadas como provisão e envia uma notificação quando o vencimento é hoje ou já passou. A notificação mostra a descrição e o valor da conta. O identificador da transação é usado para que a mesma conta atualize a notificação existente em vez de gerar várias notificações simultâneas.

O canal Android se chama “Lembretes de Faturas e Contas”.

---

## 10. API disponível

Todas as rotas funcionais do aplicativo, com exceção do webhook, esperam o cabeçalho `X-User-ID` com um UUID válido.

| Método | Rota | Função |
|---|---|---|
| GET | `/categories` | Lista as categorias do usuário. |
| POST | `/categories` | Cria uma categoria personalizada. |
| PUT | `/categories/{id}` | Atualiza uma categoria personalizada. |
| DELETE | `/categories/{id}` | Exclui a categoria e migra suas transações para “Outros”. |
| GET | `/transactions` | Lista transações por mês, busca, categoria e cartão. |
| POST | `/transactions` | Cria lançamento simples, parcelado ou fixo por período. |
| PUT | `/transactions/{id}` | Atualiza uma transação e marca a edição do usuário. |
| DELETE | `/transactions/{id}` | Exclui uma transação. |
| GET | `/summary` | Calcula saldo, receitas, despesas, provisões, planejamento, categorias e metas. |
| GET | `/summary/top-categories` | Lista as categorias com maior consumo. |
| GET | `/summary/trend` | Retorna a evolução dos últimos seis meses até o período escolhido. |
| GET | `/credit-cards` | Lista cartões com fatura atual e limite disponível. |
| POST | `/credit-cards` | Cadastra um cartão manual. |
| PUT | `/credit-cards/{id}` | Atualiza um cartão. |
| DELETE | `/credit-cards/{id}` | Exclui um cartão pertencente ao usuário. |
| GET | `/budgets` | Lista metas de um período `YYYY-MM`. |
| POST | `/budgets` | Cria ou atualiza uma meta pelo nome e período. |
| DELETE | `/budgets/{id}` | Exclui uma meta. |
| POST | `/pluggy/connect-token` | Gera token para criar ou corrigir uma conexão Pluggy. |
| POST | `/pluggy/items` | Registra uma conexão concluída e inicia a importação. |
| GET | `/pluggy/connections` | Lista conexões com contas, estado e datas de sincronização. |
| POST | `/pluggy/sync` | Coloca todas as conexões do usuário na fila de importação. |
| DELETE | `/pluggy/connections/{item_id}` | Remove a conexão e os dados importados relacionados. |
| POST | `/webhooks/pluggy` | Recebe e agenda o processamento de eventos da Pluggy. |

A documentação interativa padrão do FastAPI também fica disponível quando o backend está em execução, normalmente em `/docs` e `/redoc`.

---

## 11. Dados armazenados

| Entidade | Conteúdo principal |
|---|---|
| `users` | Identificador e e-mail técnico do usuário. |
| `categories` | Nome, ícone, tipo, indicação de categoria padrão e proprietário. |
| `transactions` | Valor, tipo, categoria, descrição, data, provisão, pagamento, cartão, fatura, origem e metadados Pluggy. |
| `credit_cards` | Nome, limite, fechamento, vencimento, origem e identificadores Pluggy. |
| `budgets` | Nome, limite, mês e conjunto de categorias da meta. |
| `pluggy_connections` | Instituição, estado, erros e datas de atualização da conexão. |
| `financial_accounts` | Conta, tipo, subtipo, saldo, moeda e instituição de origem. |
| `pluggy_webhook_events` | Histórico idempotente dos webhooks e seu processamento. |

As chaves estrangeiras associam os dados ao usuário e removem registros dependentes quando aplicável. Há índices para consultas por usuário, período, categoria, conta Pluggy e identificador externo de transação.

---

## 12. Tratamento de estados e erros

As telas principais possuem estados de carregamento, sucesso e erro. Durante requisições são mostrados indicadores de progresso; falhas oferecem mensagem e, nas consultas principais, botão para tentar novamente. Ações de criação, edição, exclusão, sincronização e efetivação exibem mensagens rápidas ao usuário.

O backend valida propriedade dos recursos para impedir que um UUID de usuário acesse categorias, transações, cartões, metas ou conexões pertencentes a outro usuário. Também valida formato do mês, valores positivos, limites de texto, dias de cartão, categoria associada, forma de pagamento e existência dos recursos relacionados.

---

## 13. Arquitetura e tecnologias

### Aplicativo Android

- Kotlin e Java 17;
- Jetpack Compose e Material 3;
- Navigation Compose;
- ViewModel, StateFlow e corrotinas;
- Retrofit, Gson e OkHttp;
- Koin para injeção de dependências;
- WorkManager para lembretes periódicos;
- Coil disponível para carregamento de imagens;
- suporte mínimo ao Android 8.0 (API 26) e alvo Android 14 (API 34).

### Backend

- Python e FastAPI;
- Pydantic para validação dos contratos;
- cliente Supabase para PostgreSQL;
- cliente HTTP para a API Pluggy;
- tarefas em segundo plano do FastAPI para importações e webhooks;
- configuração por variáveis de ambiente;
- implantação preparada para Vercel.

### Organização do Android

O código segue separação por camadas:

- `domain/model`: modelos usados pelo aplicativo;
- `domain/repository`: contratos de acesso aos dados;
- `data/api`: rotas e objetos enviados à API;
- `data/repository`: implementação, conversão de erros e chamada do serviço;
- `data/di`: configuração de rede, dependências e ViewModels;
- `presentation/ui`: telas e estado de apresentação;
- `service`: trabalho periódico de notificações.

---

## 14. Segurança e limitações atuais

O aplicativo está configurado para uso pessoal/desenvolvimento e envia sempre o UUID fixo `00000000-0000-0000-0000-000000000001` no cabeçalho `X-User-ID`. O backend cria automaticamente um usuário e suas categorias padrão quando recebe um UUID ainda inexistente.

Esse cabeçalho identifica o proprietário dos dados, mas não comprova identidade. Atualmente não há tela de cadastro, login, recuperação de senha, sessão autenticada ou validação de JWT do Supabase. Antes de distribuir o aplicativo para várias pessoas ou usar dados bancários de terceiros, é necessário implementar autenticação real e validar o token no backend.

Outros pontos do estado atual:

- a URL da API está fixa no código Android como `https://saldo-sigma.vercel.app/`;
- o manifesto permite tráfego HTTP sem criptografia, embora a API configurada use HTTPS;
- o CORS do backend aceita qualquer origem;
- o build de release não habilita minificação;
- a repetição “Todo mês” de uma despesa fixa não possui geração contínua automática;
- a atualização manual do Open Finance importa o que já está disponível na Pluggy, sem forçar nova coleta na instituição;
- a notificação periódica depende das regras do WorkManager e não tem garantia de execução em um horário exato;
- não há modo offline local: as operações dependem da API, exceto pela visualização transitória de estado já carregado em memória.

---

## 15. Verificações automatizadas existentes

Os testes Android verificam comportamentos de concorrência e carregamento, incluindo:

- início paralelo das requisições independentes do Dashboard;
- espera da busca até o usuário parar de digitar;
- descarte de uma resposta antiga depois da troca de mês.

Os testes do backend verificam pontos centrais da integração Pluggy, como:

- importação em lotes e preservação de edições locais;
- sincronização de todas as conexões pertencentes ao usuário;
- importação de todas as contas de uma conexão;
- isolamento de falhas entre instituições;
- escopo das contas por usuário e conexão;
- compatibilidade com diferentes formatos de resposta da API de contas.

---

## 16. Fluxo típico de uso

1. O aplicativo abre no Dashboard do mês atual.
2. O usuário cadastra manualmente transações e cartões ou conecta uma instituição pelo Open Finance.
3. Receitas e despesas realizadas atualizam os indicadores, enquanto provisões aparecem como valores futuros.
4. Compras no cartão são atribuídas ao ciclo da fatura e reduzem o limite disponível.
5. Categorias organizam os gastos e alimentam gráficos, filtros e metas.
6. Metas comparam o consumo das categorias escolhidas ao limite mensal.
7. Contas vencidas ou com vencimento no dia geram lembretes periódicos.
8. Dados Open Finance são atualizados por importação manual e por webhooks da Pluggy.
