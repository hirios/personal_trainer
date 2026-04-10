/**
 * workout-builder.js — Lógica de estado do montador de fichas de treino.
 * Gerencia o array de exercícios em memória, auto-save e integração com SortableJS.
 *
 * Dependências: api.js, toast.js
 *
 * Uso:
 *   WorkoutBuilder.init(workoutId)  // após criar/carregar a ficha
 *   WorkoutBuilder.addExercise(data)
 *   WorkoutBuilder.removeExercise(localId)
 *   WorkoutBuilder.updateExercise(localId, fields)
 *   WorkoutBuilder.getPayload()
 */

const WorkoutBuilder = (() => {
  // Estado interno
  let _workoutId   = null;   // UUID da ficha no backend (null = ficha nova ainda não salva)
  let _exercises   = [];     // Array de exercícios em memória
  let _nextLocalId = 1;      // ID local temporário (antes de ter UUID do backend)
  let _autoSaveTimer = null;
  let _isDirty     = false;
  let _sortable    = null;
  let _dragEndedAt = 0;   // timestamp do último fim de drag (ms)

  // Callbacks registráveis pelo host
  let _onRender    = null;   // chamado sempre que _exercises muda
  let _onSaveStatus = null;  // chamado com 'saving' | 'saved' | 'error'

  // ────────────────── API Pública ──────────────────

  /**
   * Inicializa o builder com uma ficha existente (edição) ou do zero (criação).
   * @param {string|null} workoutId - UUID da ficha, ou null para nova.
   * @param {Array} existingExercises - Exercícios já carregados do backend.
   * @param {Function} onRender - Callback chamado ao mudar estado.
   * @param {Function} onSaveStatus - Callback('saving'|'saved'|'error').
   */
  function init(workoutId, existingExercises = [], onRender = null, onSaveStatus = null) {
    _workoutId    = workoutId;
    _onRender     = onRender;
    _onSaveStatus = onSaveStatus;
    _exercises    = existingExercises.map((ex) => ({
      ...ex,
      _localId: _nextLocalId++,
    }));
    _isDirty = false;
    _render();
  }

  /**
   * Adiciona um exercício ao final da lista.
   * Se já houver workoutId, persiste via API.
   */
  async function addExercise(data) {
    const localId = _nextLocalId++;
    const position = _exercises.length + 1;

    const exercise = {
      _localId:       localId,
      id:             null,          // preenchido após resposta da API
      exercise_name:  data.exercise_name || "Novo exercício",
      muscle_group:   data.muscle_group || null,
      sets:           data.sets || 3,
      reps:           data.reps || "12",
      load:           data.load || "",
      rest_seconds:   data.rest_seconds || 60,
      technique_notes: data.technique_notes || "",
      video_url:      data.video_url || "",
      position,
      superset_group: null,
    };

    _exercises.push(exercise);
    _render();

    if (_workoutId) {
      const result = await Api.post(`/api/workouts/${_workoutId}/exercises`, {
        exercise_name:   exercise.exercise_name,
        muscle_group:    exercise.muscle_group,
        sets:            exercise.sets,
        reps:            exercise.reps,
        load:            exercise.load,
        rest_seconds:    exercise.rest_seconds,
        technique_notes: exercise.technique_notes,
        video_url:       exercise.video_url,
        position,
      });

      if (result.success) {
        // Preenche o UUID real do backend
        const idx = _exercises.findIndex((e) => e._localId === localId);
        if (idx !== -1) {
          _exercises[idx].id = result.data.exercise.id;
        }
      }
    }
  }

  /**
   * Remove exercício pelo localId.
   */
  async function removeExercise(localId) {
    const ex = _exercises.find((e) => e._localId === localId);
    if (!ex) return;

    _exercises = _exercises.filter((e) => e._localId !== localId);
    _reindexPositions();
    _render();

    if (_workoutId && ex.id) {
      await Api.del(`/api/workouts/${_workoutId}/exercises/${ex.id}`);
    }
  }

  /**
   * Atualiza campos de um exercício e agenda auto-save.
   */
  function updateExercise(localId, fields) {
    const idx = _exercises.findIndex((e) => e._localId === localId);
    if (idx === -1) return;
    _exercises[idx] = { ..._exercises[idx], ...fields };
    _isDirty = true;
    _scheduleAutoSave();
  }

  /**
   * Atualiza order após drag-and-drop.
   * newOrder = array de localIds na nova ordem.
   */
  async function reorderExercises(newOrder) {
    const map = Object.fromEntries(_exercises.map((e) => [e._localId, e]));
    _exercises = newOrder.map((lid, i) => ({
      ...map[lid],
      position: i + 1,
    }));

    // O SortableJS já moveu os nós no DOM — só atualiza os badges de posição,
    // sem reconstruir o HTML (evita flash visual e reset de scroll).
    _exercises.forEach((ex) => {
      const card = document.querySelector(`[data-local-id="${ex._localId}"]`);
      if (card) {
        const badge = card.querySelector(".pos-badge");
        if (badge) badge.textContent = ex.position;
      }
    });

    if (_workoutId) {
      const items = _exercises
        .filter((e) => e.id)
        .map((e) => ({ id: e.id, position: e.position }));
      if (items.length) {
        await Api.post(`/api/workouts/${_workoutId}/exercises/reorder`, items);
      }
    }
  }

  /**
   * Retorna o payload atual para enviar ao criar/salvar a ficha.
   */
  function getPayload() {
    return _exercises.map(({ _localId, id, ...rest }) => rest);
  }

  /**
   * Define o workoutId após a ficha ser criada no backend.
   */
  function setWorkoutId(id) {
    _workoutId = id;
  }

  /**
   * Inicializa o SortableJS na lista de exercícios.
   * @param {HTMLElement} listEl - Elemento <ul> ou <div> que contém os itens.
   * @param {Function} getLocalId - Função que extrai o localId de um elemento DOM.
   */
  function initSortable(listEl, getLocalId) {
    if (typeof Sortable === "undefined") {
      console.warn("[WorkoutBuilder] SortableJS não carregado.");
      return;
    }
    if (_sortable) _sortable.destroy();

    _sortable = Sortable.create(listEl, {
      handle:         ".drag-handle",
      animation:      150,
      ghostClass:     "sortable-ghost",
      scroll:         true,
      scrollSensitivity: 80,
      scrollSpeed:    20,
      onStart() {
        listEl.classList.add("is-sorting");
      },
      onEnd() {
        listEl.classList.remove("is-sorting");
        _dragEndedAt = Date.now();
        const newOrder = Array.from(listEl.children).map((el) =>
          parseInt(el.dataset.localId)
        );
        reorderExercises(newOrder);
      },
    });
  }

  // ────────────────── Auto-save ──────────────────

  function _scheduleAutoSave() {
    clearTimeout(_autoSaveTimer);
    _autoSaveTimer = setTimeout(_doAutoSave, 2000);
    if (_onSaveStatus) _onSaveStatus("pending");
  }

  async function _doAutoSave() {
    if (!_workoutId || !_isDirty) return;
    if (_onSaveStatus) _onSaveStatus("saving");

    // Auto-save: persiste cada exercício modificado que já tem ID
    let allOk = true;
    for (const ex of _exercises) {
      if (!ex.id) continue;
      const result = await Api.patch(
        `/api/workouts/${_workoutId}/exercises/${ex.id}`,
        {
          exercise_name:   ex.exercise_name,
          muscle_group:    ex.muscle_group,
          sets:            ex.sets,
          reps:            ex.reps,
          load:            ex.load,
          rest_seconds:    ex.rest_seconds,
          technique_notes: ex.technique_notes,
          video_url:       ex.video_url,
          superset_group:  ex.superset_group,
        }
      );
      if (!result.success) allOk = false;
    }

    _isDirty = false;
    if (_onSaveStatus) _onSaveStatus(allOk ? "saved" : "error");
  }

  // ────────────────── Helpers internos ──────────────────

  function _reindexPositions() {
    _exercises.forEach((ex, i) => { ex.position = i + 1; });
  }

  function _render() {
    if (_onRender) _onRender([..._exercises]);
  }

  // ────────────────── Getters de leitura ──────────────────

  function getExercises() {
    return [..._exercises];
  }

  function getWorkoutId() {
    return _workoutId;
  }

  /** Retorna true se um drag terminou há menos de 300ms (protege contra cliques residuais). */
  function justFinishedDrag() {
    return Date.now() - _dragEndedAt < 300;
  }

  return {
    init,
    addExercise,
    removeExercise,
    updateExercise,
    reorderExercises,
    getPayload,
    setWorkoutId,
    initSortable,
    getExercises,
    getWorkoutId,
    justFinishedDrag,
  };
})();
