import { useId, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import type { CreateCaseRequest } from '../api/types/cases'
import {
  createEmptyFactRow,
  rowsToFacts,
  type FactRow,
} from '../features/cases/knownFactsForm'
import { useCreateCaseMutation } from '../features/cases/useCreateCaseMutation'
import styles from './NewCasePage.module.css'

type FieldErrors = {
  question?: string
}

export function NewCasePage() {
  const navigate = useNavigate()
  const mutation = useCreateCaseMutation()
  const questionId = useId()
  const userNameId = useId()
  const localNumberId = useId()
  const questionRef = useRef<HTMLTextAreaElement>(null)

  const [question, setQuestion] = useState('')
  const [userName, setUserName] = useState('')
  const [localNumber, setLocalNumber] = useState('')
  const [factRows, setFactRows] = useState<FactRow[]>([])
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})

  const busy = mutation.isPending

  function validate(): FieldErrors {
    const errors: FieldErrors = {}
    if (question.trim().length < 1) {
      errors.question = 'Question or issue description is required.'
    }
    return errors
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const errors = validate()
    setFieldErrors(errors)
    if (errors.question) {
      questionRef.current?.focus()
      return
    }
    if (busy) {
      return
    }

    const knownFacts = rowsToFacts(factRows)
    const body: CreateCaseRequest = {
      question: question.trim(),
    }
    if (userName.trim()) {
      body.user_name = userName.trim()
    }
    if (localNumber.trim()) {
      body.local_number = localNumber.trim()
    }
    if (Object.keys(knownFacts).length > 0) {
      body.known_facts = knownFacts
    }

    mutation.mutate(body, {
      onSuccess: (response) => {
        const caseUuid = response.case.case_uuid
        void navigate(`/cases/${caseUuid}`)
      },
    })
  }

  const apiError =
    mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error
        ? 'Unable to create the case.'
        : null

  return (
    <section className={styles.page} aria-labelledby="new-case-heading">
      <h1 id="new-case-heading" className={styles.heading}>
        New Case
      </h1>
      <p className={styles.intro}>
        Create a persistent grievance case workspace. Creation does not start
        chat, retrieval, or analysis.
      </p>

      <form
        className={styles.form}
        onSubmit={handleSubmit}
        noValidate
        aria-busy={busy || undefined}
      >
        <div className={styles.field}>
          <label htmlFor={questionId}>
            Question or issue description{' '}
            <span className={styles.required} aria-hidden="true">
              *
            </span>
          </label>
          <p id={`${questionId}-help`} className={styles.help}>
            Required. Becomes the case title (truncated) and initial issue context.
          </p>
          <textarea
            id={questionId}
            ref={questionRef}
            name="question"
            required
            rows={5}
            value={question}
            aria-required="true"
            aria-invalid={fieldErrors.question ? true : undefined}
            aria-describedby={
              fieldErrors.question
                ? `${questionId}-help ${questionId}-error`
                : `${questionId}-help`
            }
            disabled={busy}
            onChange={(event) => {
              setQuestion(event.target.value)
              if (fieldErrors.question) {
                setFieldErrors((current) => ({
                  ...current,
                  question: undefined,
                }))
              }
            }}
          />
          {fieldErrors.question ? (
            <p id={`${questionId}-error`} className={styles.fieldError} role="alert">
              {fieldErrors.question}
            </p>
          ) : null}
        </div>

        <div className={styles.field}>
          <label htmlFor={userNameId}>Steward name</label>
          <p id={`${userNameId}-help`} className={styles.help}>
            Optional. Stored as the case user/steward name.
          </p>
          <input
            id={userNameId}
            name="user_name"
            type="text"
            value={userName}
            aria-describedby={`${userNameId}-help`}
            disabled={busy}
            onChange={(event) => setUserName(event.target.value)}
            autoComplete="name"
          />
        </div>

        <div className={styles.field}>
          <label htmlFor={localNumberId}>Local number</label>
          <p id={`${localNumberId}-help`} className={styles.help}>
            Optional. Local or case reference number.
          </p>
          <input
            id={localNumberId}
            name="local_number"
            type="text"
            value={localNumber}
            aria-describedby={`${localNumberId}-help`}
            disabled={busy}
            onChange={(event) => setLocalNumber(event.target.value)}
            autoComplete="off"
          />
        </div>

        <fieldset className={styles.factsBox}>
          <legend>Known facts (optional)</legend>
          <p className={styles.help}>
            Optional key/value facts stored on the case at creation. You can
            edit them later in the workspace.
          </p>
          {factRows.map((row, index) => (
            <div key={row.id} className={styles.factRow}>
              <div className={styles.field}>
                <label htmlFor={`${row.id}-key`}>Key</label>
                <input
                  id={`${row.id}-key`}
                  name={`known_facts_key_${index}`}
                  value={row.key}
                  disabled={busy}
                  onChange={(event) =>
                    setFactRows((current) =>
                      current.map((item) =>
                        item.id === row.id
                          ? { ...item, key: event.target.value }
                          : item,
                      ),
                    )
                  }
                />
              </div>
              <div className={styles.field}>
                <label htmlFor={`${row.id}-value`}>Value</label>
                <input
                  id={`${row.id}-value`}
                  name={`known_facts_value_${index}`}
                  value={row.value}
                  disabled={busy}
                  onChange={(event) =>
                    setFactRows((current) =>
                      current.map((item) =>
                        item.id === row.id
                          ? { ...item, value: event.target.value }
                          : item,
                      ),
                    )
                  }
                />
              </div>
              <button
                type="button"
                className={styles.secondaryButton}
                disabled={busy}
                onClick={() =>
                  setFactRows((current) =>
                    current.filter((item) => item.id !== row.id),
                  )
                }
              >
                Remove
              </button>
            </div>
          ))}
          <button
            type="button"
            className={styles.secondaryButton}
            disabled={busy}
            onClick={() =>
              setFactRows((current) => [...current, createEmptyFactRow()])
            }
          >
            Add fact
          </button>
        </fieldset>

        {apiError ? (
          <p className={styles.alert} role="alert">
            {apiError}
          </p>
        ) : null}

        <div className={styles.actions}>
          <button type="submit" className={styles.submit} disabled={busy}>
            {busy ? 'Creating case…' : 'Create case'}
          </button>
          <Link className={styles.cancel} to="/cases">
            Cancel
          </Link>
        </div>
      </form>

      <p className={styles.note}>
        After create, you will enter the case workspace. Conversation remains a
        later milestone — this form does not send the first chat interaction.
      </p>
    </section>
  )
}
