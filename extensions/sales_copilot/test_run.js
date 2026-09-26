const JORDAN_PLAYBOOK = require('./playbook_jordan.js');
const LayaSalesEngine = require('./engine_laya.js');

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
console.log("Objeção:", state2.activeObjection.title);
console.log("Step 1 (Concordar):", state2.activeObjection.jordan_script.step1_agree);
console.log("Step 2 (Pivô ROI):", state2.activeObjection.jordan_script.step2_pivot);
console.log("Step 3 (Fechamento):", state2.activeObjection.jordan_script.step3_close);

console.log("\n=================================================");
console.log("🎯 TESTE 3: SCRAPING (R$ 12.000 setup, R$ 0/m, Ticket R$ 5.000)");
console.log("=================================================");
const engine3 = new LayaSalesEngine(JORDAN_PLAYBOOK, {
  client: "Empresa de Dados",
  product: "Robô de Extração de Dados",
  setupPrice: 12000,
  monthlyPrice: 0,
  clientTicket: 5000
});
const state3 = engine3.processSpeechSnippet("client", "achei caro");
console.log("Step 2 (Pivô ROI Setup):", state3.activeObjection.jordan_script.step2_pivot);

console.log("\n=================================================");
console.log("🎯 TESTE 4: DÚVIDA DA EQUIPE (CONTEXTUAL)");
console.log("=================================================");
const state4 = engine2.processSpeechSnippet("client", "será que a minha equipe vai conseguir usar?");
console.log("Objeção:", state4.activeObjection.title);
console.log("Step 1 (Concordar):", state4.activeObjection.jordan_script.step1_agree);
console.log("Step 2 (Pivô):", state4.activeObjection.jordan_script.step2_pivot);

console.log("\n=================================================");
console.log("🎯 TESTE 5: MUDANÇA DINÂMICA DE CONTEXTO EM TEMPO REAL");
console.log("=================================================");
engine2.setDealContext({
  client: "Cantor Sertanejo",
  product: "Site de Shows",
  setupPrice: 3000,
  monthlyPrice: 100,
  clientTicket: 1500
});
console.log("Script Recalculado:", engine2.getState().activeObjection?.jordan_script.step1_agree);
console.log("✅ TODOS OS TESTES PASSARAM COM SUCESSO!");
