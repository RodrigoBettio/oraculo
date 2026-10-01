const JORDAN_PLAYBOOK = require('./playbook_jordan.js');
const LayaSalesEngine = require('./engine_laya.js');

function assert(condition, message) {
  if (!condition) {
    console.error(`❌ FALHA: ${message}`);
    process.exit(1);
  }
}

console.log("=================================================");
console.log("🎯 TESTE 1: PREÇO SIMBÓLICO (R$ 1) — CASO DO USUÁRIO");
console.log("=================================================");
const engine1 = new LayaSalesEngine(JORDAN_PLAYBOOK, {
  client: "Cliente Teste",
  product: "Oferta Simbólica",
  setupPrice: 1,
  monthlyPrice: 0,
  clientTicket: 1
});
const state1 = engine1.processSpeechSnippet("client", "achei 1 real muito caro");
assert(state1.activeObjection && state1.activeObjection.id === "PRECO_ALTO", "Deveria detectar PRECO_ALTO");
console.log("Objeção:", state1.activeObjection.title);
console.log("Step 1 (Concordar):", state1.activeObjection.jordan_script.step1_agree);
console.log("Step 2 (Pivô):", state1.activeObjection.jordan_script.step2_pivot);
console.log("Step 3 (Fechamento):", state1.activeObjection.jordan_script.step3_close);

console.log("\n=================================================");
console.log("🎯 TESTE 2: OFICINA MECÂNICA (R$ 2.000 setup, R$ 150/m, Ticket R$ 250)");
console.log("=================================================");
const engine2 = new LayaSalesEngine(JORDAN_PLAYBOOK, {
  client: "Oficina Mecânica",
  product: "Landing Page + Agendamento WhatsApp",
  setupPrice: 2000,
  monthlyPrice: 150,
  clientTicket: 250
});
const state2 = engine2.processSpeechSnippet("client", "o valor está um pouco salgado para o momento");
assert(state2.activeObjection && state2.activeObjection.id === "PRECO_ALTO", "Deveria detectar PRECO_ALTO");
console.log("Objeção:", state2.activeObjection.title);
console.log("Step 2 (Pivô ROI):", state2.activeObjection.jordan_script.step2_pivot);

console.log("\n=================================================");
console.log("🎯 TESTE 3: FILTRO DE NEGAÇÃO (NÃO DISPARA FALSOS POSITIVOS)");
console.log("=================================================");
const engineNeg = new LayaSalesEngine(JORDAN_PLAYBOOK);
// Teste A: "não achei caro" não deve acionar objeção de preço
const stateNeg1 = engineNeg.processSpeechSnippet("client", "achei muito legal o projeto, não achei caro");
assert(!stateNeg1.activeObjection || stateNeg1.activeObjection.id !== "PRECO_ALTO", "Não deve acionar PRECO_ALTO com negação 'não achei caro'");
console.log("✅ 'não achei caro' -> Nenhuma objeção de preço disparada!");

// Teste B: "o preço não é problema"
const stateNeg2 = engineNeg.processSpeechSnippet("client", "o preço não é problema para nós");
assert(!stateNeg2.activeObjection || stateNeg2.activeObjection.id !== "PRECO_ALTO", "Não deve acionar PRECO_ALTO com 'o preço não é problema'");
console.log("✅ 'o preço não é problema' -> Ignorado com sucesso!");

console.log("\n=================================================");
console.log("🎯 TESTE 4: 5 NOVAS OBJEÇÕES DO JORDAN BELFORD");
console.log("=================================================");
const engineObj = new LayaSalesEngine(JORDAN_PLAYBOOK, {
  client: "Clínica Médica",
  product: "IA de Triagem e Agendamento",
  setupPrice: 3000,
  monthlyPrice: 350,
  clientTicket: 400
});

// 4.1 VOU_PENSAR
const sVouPensar = engineObj.processSpeechSnippet("client", "vou pensar com calma e te retorno por email");
assert(sVouPensar.activeObjection && sVouPensar.activeObjection.id === "VOU_PENSAR", "Deveria detectar VOU_PENSAR");
console.log("✅ [VOU_PENSAR]:", sVouPensar.activeObjection.jordan_script.step2_pivot);

// 4.2 FALTA_PROVA_SOCIAL
const sProvaSocial = engineObj.processSpeechSnippet("client", "você tem algum case de sucesso ou outros clientes pra me mostrar?");
assert(sProvaSocial.activeObjection && sProvaSocial.activeObjection.id === "FALTA_PROVA_SOCIAL", "Deveria detectar FALTA_PROVA_SOCIAL");
console.log("✅ [FALTA_PROVA_SOCIAL]:", sProvaSocial.activeObjection.jordan_script.step1_agree);

// 4.3 MEDO_LGPD_SEGURANCA
const sLgpd = engineObj.processSpeechSnippet("client", "e a lgpd como fica? meus dados e dos pacientes ficam seguros?");
assert(sLgpd.activeObjection && sLgpd.activeObjection.id === "MEDO_LGPD_SEGURANCA", "Deveria detectar MEDO_LGPD_SEGURANCA");
console.log("✅ [MEDO_LGPD_SEGURANCA]:", sLgpd.activeObjection.jordan_script.step2_pivot);

// 4.4 INTEGRACAO_SISTEMA
const sIntegracao = engineObj.processSpeechSnippet("client", "isso integra com meu erp e com o sistema atual?");
assert(sIntegracao.activeObjection && sIntegracao.activeObjection.id === "INTEGRACAO_SISTEMA", "Deveria detectar INTEGRACAO_SISTEMA");
console.log("✅ [INTEGRACAO_SISTEMA]:", sIntegracao.activeObjection.jordan_script.step2_pivot);

// 4.5 NAO_E_MOMENTO
const sMomento = engineObj.processSpeechSnippet("client", "gostei mas não é o momento certo agora, vamos deixar pro mês que vem");
assert(sMomento.activeObjection && sMomento.activeObjection.id === "NAO_E_MOMENTO", "Deveria detectar NAO_E_MOMENTO");
console.log("✅ [NAO_E_MOMENTO]:", sMomento.activeObjection.jordan_script.step2_pivot);

console.log("\n=================================================");
console.log("🎯 TESTE 5: 4 NOVOS SINAIS DE COMPRA (GREEN FLAGS)");
console.log("=================================================");
const engineSignals = new LayaSalesEngine(JORDAN_PLAYBOOK);

// 5.1 PEDIDO_DEMO
const sDemo = engineSignals.processSpeechSnippet("client", "posso testar antes de fechar para experimentar?");
assert(sDemo.activeBuyingSignal && sDemo.activeBuyingSignal.id === "PEDIDO_DEMO", "Deveria detectar PEDIDO_DEMO");
console.log("✅ [PEDIDO_DEMO]:", sDemo.activeBuyingSignal.jordan_alert);

// 5.2 PERGUNTA_SUPORTE_ONBOARDING
const sSuporte = engineSignals.processSpeechSnippet("client", "como funciona o suporte de vocês e o acompanhamento no dia a dia?");
assert(sSuporte.activeBuyingSignal && sSuporte.activeBuyingSignal.id === "PERGUNTA_SUPORTE_ONBOARDING", "Deveria detectar PERGUNTA_SUPORTE_ONBOARDING");
console.log("✅ [PERGUNTA_SUPORTE_ONBOARDING]:", sSuporte.activeBuyingSignal.jordan_alert);

// 5.3 INCLUSAO_TERCEIROS_POSITIVA
const sSocios = engineSignals.processSpeechSnippet("client", "posso trazer meu sócio para a próxima reunião para vermos juntos?");
assert(sSocios.activeBuyingSignal && sSocios.activeBuyingSignal.id === "INCLUSAO_TERCEIROS_POSITIVA", "Deveria detectar INCLUSAO_TERCEIROS_POSITIVA");
console.log("✅ [INCLUSAO_TERCEIROS_POSITIVA]:", sSocios.activeBuyingSignal.jordan_alert);

// 5.4 COMPARACAO_FAVORAVEL
const sComp = engineSignals.processSpeechSnippet("client", "gostei muito mais do que o concorrente, vocês são melhores");
assert(sComp.activeBuyingSignal && sComp.activeBuyingSignal.id === "COMPARACAO_FAVORAVEL", "Deveria detectar COMPARACAO_FAVORAVEL");
console.log("✅ [COMPARACAO_FAVORAVEL]:", sComp.activeBuyingSignal.jordan_alert);

console.log("\n=================================================");
console.log("🎯 TESTE 6: MUDANÇA DINÂMICA DE CONTEXTO");
console.log("=================================================");
engine2.setDealContext({
  client: "Cantor Sertanejo",
  product: "Site de Shows",
  setupPrice: 3000,
  monthlyPrice: 100,
  clientTicket: 1500
});
const stateContext = engine2.getState();
console.log("Script Recalculado:", stateContext.dealContext.client);

console.log("\n=================================================");
console.log("🎉 TODOS OS TESTES PASSARAM COM 100% DE SUCESSO!");
console.log("=================================================");
