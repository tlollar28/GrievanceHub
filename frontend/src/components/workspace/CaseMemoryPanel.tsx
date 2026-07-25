import type { CaseMemoryFoundation } from '../../api/types/workspace'
import styles from './CaseRail.module.css'

type Props = {
  memory: CaseMemoryFoundation | null | undefined
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === 'string')
}

export function CaseMemoryPanel({ memory }: Props) {
  if (!memory || memory.restored_from === 'unavailable') {
    return (
      <section className={styles.section} aria-labelledby="case-memory-heading">
        <h2 id="case-memory-heading" className={styles.heading}>
          Case Memory
        </h2>
        <p className={styles.empty}>
          Case Memory is not available for this case yet. Memory is
          system-maintained and is not a full conversation transcript.
        </p>
      </section>
    )
  }

  const openQuestions = asStringList(memory.open_questions)
  const outstanding = asStringList(memory.outstanding_issues)
  const recommendation =
    typeof memory.current_recommendation === 'string'
      ? memory.current_recommendation
      : null
  const step =
    typeof memory.current_grievance_step === 'string'
      ? memory.current_grievance_step
      : null
  const workflow =
    memory.workflow && typeof memory.workflow === 'object'
      ? (memory.workflow as Record<string, unknown>)
      : null
  const explicitState =
    workflow && typeof workflow.explicit_state === 'string'
      ? workflow.explicit_state
      : null

  return (
    <section className={styles.section} aria-labelledby="case-memory-heading">
      <h2 id="case-memory-heading" className={styles.heading}>
        Case Memory
      </h2>
      <p className={styles.disclaimer}>
        System-maintained understanding of the case. This is not a full
        transcript.
        {memory.full_transcript_embedded === false
          ? ' Full conversation history is not embedded here.'
          : ''}
      </p>

      <dl className={styles.metaList}>
        {memory.restored_from ? (
          <div>
            <dt>Restored from</dt>
            <dd>{memory.restored_from}</dd>
          </div>
        ) : null}
        {step ? (
          <div>
            <dt>Grievance step</dt>
            <dd>{step}</dd>
          </div>
        ) : null}
        {explicitState ? (
          <div>
            <dt>Workflow state</dt>
            <dd>{explicitState}</dd>
          </div>
        ) : null}
        {typeof memory.reopen_count === 'number' ? (
          <div>
            <dt>Reopen count</dt>
            <dd>{memory.reopen_count}</dd>
          </div>
        ) : null}
      </dl>

      {recommendation ? (
        <div>
          <h3 className={styles.subheading}>Current recommendation</h3>
          <p className={styles.bodyText}>{recommendation}</p>
          <p className={styles.disclaimer}>
            Generated assessments are not source authority.
          </p>
        </div>
      ) : null}

      {openQuestions.length > 0 ? (
        <div>
          <h3 className={styles.subheading}>Open questions</h3>
          <ul className={styles.list}>
            {openQuestions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className={styles.empty}>No open questions in Case Memory.</p>
      )}

      {outstanding.length > 0 ? (
        <div>
          <h3 className={styles.subheading}>Outstanding issues</h3>
          <ul className={styles.list}>
            {outstanding.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}
