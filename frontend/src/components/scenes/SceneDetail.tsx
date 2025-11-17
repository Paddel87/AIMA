import { SceneDetail } from '../../api/types'

export default function SceneDetailComp({ d }: { d: SceneDetail }) {
  const faces = d.faces ?? []
  return (
    <div className="space-y-6">
      <div>
        <div className="page-title">Szene {d.scene.index}</div>
        <div className="subtext">{d.scene.start_time}–{d.scene.end_time}s • Video {d.scene.video_id}</div>
      </div>
      <div>
        <div className="text-base font-semibold mb-2">Text</div>
        {d.asr_text && <div className="text-sm text-neutral-700">ASR: {d.asr_text}</div>}
        {d.ocr_text && <div className="text-sm text-neutral-700">OCR: {d.ocr_text}</div>}
        {!d.asr_text && !d.ocr_text && <div className="subtext">Kein Text vorhanden.</div>}
      </div>
      <div>
        <div className="text-base font-semibold mb-2">Objekte</div>
        {d.objects && d.objects.length > 0 ? (
          <div className="text-sm text-neutral-700">{d.objects.join(', ')}</div>
        ) : (
          <div className="subtext">Keine Objekte erkannt.</div>
        )}
      </div>
      <div>
        <div className="text-base font-semibold mb-2">Gesichter/Personen</div>
        {faces.length === 0 ? (
          <div className="subtext">Keine Gesichter</div>
        ) : (
          <ul className="space-y-2">
            {faces.map(f => (
              <li key={f.face_id} className="card card-pad">
                <div className="text-sm">id={f.face_id} • conf={(f.confidence ?? 0).toFixed(2)} • person={f.person_id ?? '-'}</div>
                <div className="text-xs text-neutral-600">bbox {[...f.bbox].join(',')}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}