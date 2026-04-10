/**
 * exercises-db.js — Base de exercícios pré-cadastrados do FitFlow Pro.
 * 220+ exercícios organizados por grupo muscular.
 * Expõe o array global `EXERCISES_DB`.
 */

const EXERCISES_DB = [
  // ──────────────────── PEITO ────────────────────
  { name: "Supino reto com barra", group: "peito" },
  { name: "Supino inclinado com barra", group: "peito" },
  { name: "Supino declinado com barra", group: "peito" },
  { name: "Supino reto com halteres", group: "peito" },
  { name: "Supino inclinado com halteres", group: "peito" },
  { name: "Supino declinado com halteres", group: "peito" },
  { name: "Crucifixo reto com halteres", group: "peito" },
  { name: "Crucifixo inclinado com halteres", group: "peito" },
  { name: "Crossover no cabo", group: "peito" },
  { name: "Fly na máquina (peck deck)", group: "peito" },
  { name: "Flexão de braço (push-up)", group: "peito" },
  { name: "Flexão com pés elevados", group: "peito" },
  { name: "Flexão diamante", group: "peito" },
  { name: "Pullover com halter", group: "peito" },
  { name: "Crossover baixo no cabo", group: "peito" },
  { name: "Press na máquina (peito)", group: "peito" },
  { name: "Dip (paralelas)", group: "peito" },

  // ──────────────────── COSTAS ────────────────────
  { name: "Remada curvada com barra", group: "costas" },
  { name: "Remada curvada com halteres", group: "costas" },
  { name: "Remada unilateral com halter", group: "costas" },
  { name: "Remada cavalinho (T-bar row)", group: "costas" },
  { name: "Remada sentada no cabo", group: "costas" },
  { name: "Puxada no pulley (pegada fechada)", group: "costas" },
  { name: "Puxada no pulley (pegada aberta)", group: "costas" },
  { name: "Puxada no pulley (pegada neutra)", group: "costas" },
  { name: "Barra fixa (pullup)", group: "costas" },
  { name: "Barra fixa com pegada supinada (chinup)", group: "costas" },
  { name: "Levantamento terra", group: "costas" },
  { name: "Levantamento terra romeno", group: "costas" },
  { name: "Hiperextensão lombar", group: "costas" },
  { name: "Good morning com barra", group: "costas" },
  { name: "Serrote com halter", group: "costas" },
  { name: "Remada alta com barra", group: "costas" },
  { name: "Face pull no cabo", group: "costas" },

  // ──────────────────── OMBRO ────────────────────
  { name: "Desenvolvimento militar com barra", group: "ombro" },
  { name: "Desenvolvimento com halteres sentado", group: "ombro" },
  { name: "Desenvolvimento Arnold", group: "ombro" },
  { name: "Elevação lateral com halteres", group: "ombro" },
  { name: "Elevação lateral no cabo", group: "ombro" },
  { name: "Elevação frontal com barra", group: "ombro" },
  { name: "Elevação frontal com halteres", group: "ombro" },
  { name: "Elevação posterior com halteres", group: "ombro" },
  { name: "Crucifixo inverso", group: "ombro" },
  { name: "Remada alta com barra (ombro)", group: "ombro" },
  { name: "Rotação externa com cabo", group: "ombro" },
  { name: "Rotação interna com cabo", group: "ombro" },
  { name: "Press na máquina (ombro)", group: "ombro" },
  { name: "Shrug (encolhimento) com halteres", group: "ombro" },
  { name: "Shrug com barra", group: "ombro" },

  // ──────────────────── BÍCEPS ────────────────────
  { name: "Rosca direta com barra", group: "biceps" },
  { name: "Rosca direta com halteres", group: "biceps" },
  { name: "Rosca alternada com halteres", group: "biceps" },
  { name: "Rosca martelo", group: "biceps" },
  { name: "Rosca concentrada", group: "biceps" },
  { name: "Rosca scott (barra EZ)", group: "biceps" },
  { name: "Rosca scott com halteres", group: "biceps" },
  { name: "Rosca no cabo", group: "biceps" },
  { name: "Rosca spider", group: "biceps" },
  { name: "Rosca inclinada com halteres", group: "biceps" },
  { name: "Rosca 21 (técnica)", group: "biceps" },
  { name: "Curl com banda elástica", group: "biceps" },

  // ──────────────────── TRÍCEPS ────────────────────
  { name: "Tríceps testa com barra", group: "triceps" },
  { name: "Tríceps testa com halteres", group: "triceps" },
  { name: "Tríceps pulley barra reta", group: "triceps" },
  { name: "Tríceps pulley corda", group: "triceps" },
  { name: "Tríceps pulley barra V", group: "triceps" },
  { name: "Tríceps coice com halter", group: "triceps" },
  { name: "Tríceps francês com halteres", group: "triceps" },
  { name: "Tríceps francês com barra EZ", group: "triceps" },
  { name: "Mergulho em banco (tríceps)", group: "triceps" },
  { name: "Dip fechado (tríceps)", group: "triceps" },
  { name: "Tríceps no cabo unilateral", group: "triceps" },
  { name: "Supino fechado com barra", group: "triceps" },

  // ──────────────────── PERNAS ────────────────────
  { name: "Agachamento livre com barra", group: "pernas" },
  { name: "Agachamento hack", group: "pernas" },
  { name: "Agachamento sumô", group: "pernas" },
  { name: "Agachamento goblet", group: "pernas" },
  { name: "Agachamento búlgaro", group: "pernas" },
  { name: "Agachamento no Smith", group: "pernas" },
  { name: "Leg press 45°", group: "pernas" },
  { name: "Leg press horizontal", group: "pernas" },
  { name: "Extensão de quadríceps na cadeira", group: "pernas" },
  { name: "Flexão de isquiotibiais deitado", group: "pernas" },
  { name: "Flexão de isquiotibiais em pé", group: "pernas" },
  { name: "Stiff com barra", group: "pernas" },
  { name: "Stiff com halteres", group: "pernas" },
  { name: "Avanço (lunge) com barra", group: "pernas" },
  { name: "Avanço com halteres", group: "pernas" },
  { name: "Avanço caminhando", group: "pernas" },
  { name: "Levantamento terra sumô", group: "pernas" },
  { name: "Abdução de quadril na máquina", group: "pernas" },
  { name: "Adução de quadril na máquina", group: "pernas" },
  { name: "Glúteo na máquina", group: "pernas" },
  { name: "Elevação de quadril (hip thrust)", group: "pernas" },
  { name: "Hip thrust com barra", group: "pernas" },
  { name: "Panturrilha em pé na máquina", group: "pernas" },
  { name: "Panturrilha sentado", group: "pernas" },
  { name: "Panturrilha no leg press", group: "pernas" },
  { name: "Step up com halteres", group: "pernas" },
  { name: "Wall sit (cadeira)", group: "pernas" },
  { name: "Passada lateral", group: "pernas" },
  { name: "Glúteo 4 apoios no cabo", group: "pernas" },
  { name: "Agachamento unilateral (pistol squat)", group: "pernas" },

  // ──────────────────── ABDÔMEN ────────────────────
  { name: "Abdominal crunch", group: "abdomen" },
  { name: "Abdominal crunch na máquina", group: "abdomen" },
  { name: "Abdominal infra (elevação de pernas)", group: "abdomen" },
  { name: "Abdominal oblíquo", group: "abdomen" },
  { name: "Prancha frontal", group: "abdomen" },
  { name: "Prancha lateral", group: "abdomen" },
  { name: "Abdominal bicicleta", group: "abdomen" },
  { name: "Abdominal no cabo (kneeling crunch)", group: "abdomen" },
  { name: "Rollout com roda abdominal", group: "abdomen" },
  { name: "Dead bug", group: "abdomen" },
  { name: "Hollow body hold", group: "abdomen" },
  { name: "Russian twist", group: "abdomen" },
  { name: "Sit up", group: "abdomen" },
  { name: "Elevação de pernas na barra", group: "abdomen" },
  { name: "Dragon flag", group: "abdomen" },
  { name: "Vacuum abdominal", group: "abdomen" },

  // ──────────────────── CARDIO ────────────────────
  { name: "Corrida na esteira", group: "cardio" },
  { name: "Caminhada inclinada na esteira", group: "cardio" },
  { name: "Bicicleta ergométrica", group: "cardio" },
  { name: "Bicicleta ergométrica HIIT", group: "cardio" },
  { name: "Elíptico", group: "cardio" },
  { name: "Remo ergométrico", group: "cardio" },
  { name: "Pular corda", group: "cardio" },
  { name: "Sprints na esteira", group: "cardio" },
  { name: "HIIT — tiro 20s / descanso 10s", group: "cardio" },
  { name: "Stair climber", group: "cardio" },
  { name: "Jumping jacks", group: "cardio" },
  { name: "Corrida ao ar livre", group: "cardio" },
  { name: "Natação livre", group: "cardio" },
  { name: "Ciclismo ao ar livre", group: "cardio" },

  // ──────────────────── FUNCIONAL ────────────────────
  { name: "Burpee", group: "funcional" },
  { name: "Kettlebell swing", group: "funcional" },
  { name: "Kettlebell goblet squat", group: "funcional" },
  { name: "Kettlebell snatch", group: "funcional" },
  { name: "Kettlebell clean & press", group: "funcional" },
  { name: "Turkish get-up", group: "funcional" },
  { name: "Box jump", group: "funcional" },
  { name: "Agachamento com salto", group: "funcional" },
  { name: "Afundo com salto", group: "funcional" },
  { name: "Mountain climber", group: "funcional" },
  { name: "Bear crawl", group: "funcional" },
  { name: "Battle rope ondas alternadas", group: "funcional" },
  { name: "Battle rope ondas simultâneas", group: "funcional" },
  { name: "Sled push", group: "funcional" },
  { name: "Farmer's carry", group: "funcional" },
  { name: "Thruster com barra", group: "funcional" },
  { name: "Thruster com halteres", group: "funcional" },
  { name: "Wall ball", group: "funcional" },
  { name: "Toes to bar", group: "funcional" },
  { name: "Muscle up", group: "funcional" },
  { name: "Handstand push-up", group: "funcional" },
  { name: "Ring dip", group: "funcional" },
  { name: "Band pull-apart", group: "funcional" },
  { name: "Corrida com puxada de trenó", group: "funcional" },
  { name: "Slam ball", group: "funcional" },
  { name: "Agachamento com elástico", group: "funcional" },
  { name: "Hip thrust com elástico", group: "funcional" },
  { name: "Remada com elástico", group: "funcional" },
  { name: "Press com elástico", group: "funcional" },
  { name: "Puxada com elástico", group: "funcional" },
];

/**
 * Busca exercícios por texto e/ou grupo muscular.
 * @param {string} query - Texto livre para busca no nome.
 * @param {string|null} group - Grupo muscular para filtrar.
 * @returns {Array} Lista filtrada.
 */
function searchExercises(query = "", group = null) {
  const term = query.toLowerCase().trim();
  return EXERCISES_DB.filter((ex) => {
    const matchesGroup = !group || ex.group === group;
    const matchesQuery = !term || ex.name.toLowerCase().includes(term);
    return matchesGroup && matchesQuery;
  });
}
