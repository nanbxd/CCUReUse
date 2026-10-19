import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, CalendarDays, ImagePlus, MapPin, Users, Check, X, ShieldCheck, Upload } from 'lucide-react'
import { api } from './api'
import { priceText } from './ListingCard'

export const eventTypes = ['Встреча', 'Конференция', 'Концерт', 'Фестиваль', 'Спорт', 'Творчество', 'Образование', 'Вечеринка']
const initial = { title: '', description: '', category: 'Встреча', location: '', capacity: '', event_date: '', end_date: '', deadline_date: '', ticket_price: '', target_budget: '', is_private: true, banner: '' }

export default function EventEditor({ user }) {
  const [form, setForm] = useState(() => ({ ...initial, is_private: !(user?.is_admin || user?.is_organizer) })), [paid, setPaid] = useState(false), [busy, setBusy] = useState(false), [uploading, setUploading] = useState(false), [error, setError] = useState(''), [imageError, setImageError] = useState('')
  const navigate = useNavigate(), privileged = user?.is_admin || user?.is_organizer
  const update = e => { const { name, type, checked, value } = e.target; setForm(f => ({ ...f, [name]: type === 'checkbox' ? checked : value })) }
  const minimum = paid && Number(form.ticket_price) > 0 ? Math.ceil(Number(form.target_budget || 0) / Number(form.ticket_price)) : 0
  async function readBanner(file) {
    if (!file) return
    setImageError('')
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 2_000_000) { setImageError('Выберите JPEG, PNG или WebP размером до 2 МБ.'); return }
    setUploading(true)
    try {
      const data = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error('Не удалось прочитать изображение.')); reader.readAsDataURL(file) })
      await new Promise((resolve, reject) => { const image = new Image(); image.onload = resolve; image.onerror = () => reject(new Error('Файл не удалось открыть как изображение.')); image.src = data })
      setForm(f => ({ ...f, banner: data }))
    } catch (e) { setImageError(e.message) } finally { setUploading(false) }
  }
  async function submit(e) {
    e.preventDefault(); setError('')
    if (minimum > Number(form.capacity)) { setError('Для указанного бюджета нужно больше билетов, чем вмещает площадка. Измените бюджет, цену или количество мест.'); return }
    setBusy(true)
    try {
      const data = { ...form, capacity: Number(form.capacity), ticket_price: paid && privileged ? Number(form.ticket_price) : 0, target_budget: paid && privileged ? Number(form.target_budget) : 0, is_private: privileged ? form.is_private : true, event_date: new Date(form.event_date).toISOString(), end_date: new Date(form.end_date).toISOString(), deadline_date: new Date(form.deadline_date).toISOString() }
      const event = await api('/events', { method: 'POST', body: JSON.stringify(data) }); navigate(`/events/${event.id}`)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  if (!user) return <main className="container simple-page"><span className="section-label">CASPIANHUB / СОЗДАНИЕ СОБЫТИЯ</span><h1>Начните с аккаунта</h1><p>Войдите, чтобы создать афишу и управлять мероприятием.</p><Link className="btn btn-primary" to="/auth?next=/events/new">Войти <ArrowRight size={18} /></Link></main>
  return <main className="event-editor container"><Link className="back-link" to="/events"><ArrowLeft size={16} /> Афиша</Link><header className="editor-header"><div><span className="section-label">CASPIANHUB / КАБИНЕТ ОРГАНИЗАТОРА</span><h1>Новое мероприятие</h1><p>От камерной встречи до большого события. Всё начинается с подробной афиши.</p></div><span className="editor-draft"><span /> Новый анонс</span></header>
    <div className="editor-layout"><form id="event-editor-form" className="editor-form" onSubmit={submit}>
      <section className="editor-section"><div className="editor-section-heading"><span>01</span><div><h2>Афиша мероприятия</h2><p>Обложка появится в афише, на главной и на странице события.</p></div></div>
        <label className={`banner-upload ${form.banner ? 'has-image' : ''}`} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); if (!uploading) readBanner(e.dataTransfer.files[0]) }}>
          {form.banner ? <><img src={form.banner} alt="Предпросмотр загруженной афиши" /><span className="banner-upload-replace"><Upload size={16} /> Заменить обложку</span></> : <><span className="banner-upload-icon"><ImagePlus size={30} /></span><strong>{uploading ? 'Загружаем изображение…' : 'Добавить обложку события'}</strong><span>Перетащите изображение или выберите файл</span><small>JPEG, PNG, WebP · до 2 МБ · рекомендуем 1600 × 900 px</small></>}
          <input type="file" aria-label="Обложка мероприятия" accept="image/jpeg,image/png,image/webp" disabled={uploading} onChange={e => { readBanner(e.target.files[0]); e.target.value = '' }} />
        </label><div className="banner-upload-help"><span>Горизонтальный формат 16:9. Важный текст разместите ближе к центру.</span>{form.banner && <button type="button" onClick={() => setForm(f => ({ ...f, banner: '' }))}><X size={14} /> Удалить</button>}</div>{imageError && <div role="alert" className="notice error">{imageError}</div>}
      </section>
      <section className="editor-section"><div className="editor-section-heading"><span>02</span><div><h2>Основная информация</h2><p>Название, формат и программа — то, что участники увидят первым.</p></div></div><div className="form-stack">
        <label>Название мероприятия <span className="field-required">*</span><input name="title" value={form.title} onChange={update} minLength={3} maxLength={120} required placeholder="Например, Caspian: конференция студенческих проектов" /><small>{form.title.length} / 120</small></label>
        <label>Формат мероприятия<select name="category" value={form.category} onChange={update}>{eventTypes.map(t => <option key={t}>{t}</option>)}</select></label>
        <label>Описание и программа <span className="field-required">*</span><textarea name="description" value={form.description} onChange={update} minLength={10} maxLength={5000} rows={7} required placeholder={'О чём мероприятие и кому оно будет интересно?\n\nПрограмма, спикеры, активности и важные детали для участников.'} /><small>До 5 000 символов. Переносы строк сохраняются.</small></label>
      </div></section>
      <section className="editor-section"><div className="editor-section-heading"><span>03</span><div><h2>Дата и площадка</h2><p>Укажите полный интервал проведения и количество доступных мест.</p></div></div><div className="form-stack"><div className="form-two"><label>Начало мероприятия *<input name="event_date" type="datetime-local" required value={form.event_date} onChange={update} /></label><label>Окончание мероприятия *<input name="end_date" type="datetime-local" min={form.event_date || undefined} required value={form.end_date} onChange={update} /></label></div><small>Часовой пояс: {Intl.DateTimeFormat().resolvedOptions().timeZone}. Билеты действуют до окончания мероприятия.</small><label>Площадка или адрес *<input name="location" value={form.location} onChange={update} required minLength={2} maxLength={300} placeholder="Название площадки, адрес или ссылка на 2GIS" /></label><div className="form-two"><label>Вместимость, человек *<input name="capacity" type="number" value={form.capacity} onChange={update} required min="1" max="100000" placeholder="Например, 500" /></label><label>Окончание регистрации / сбора *<input name="deadline_date" type="datetime-local" max={form.event_date || undefined} value={form.deadline_date} onChange={update} required /></label></div></div></section>
      <section className="editor-section"><div className="editor-section-heading"><span>04</span><div><h2>Участие и доступ</h2><p>Определите, кто увидит афишу и на каких условиях можно участвовать.</p></div></div><div className="form-stack"><fieldset className="editor-choice-group"><legend>Условия участия</legend><label className={!paid ? 'selected' : ''}><input type="radio" name="payment_mode" checked={!paid} onChange={() => setPaid(false)} /><span><strong>Бесплатно</strong><small>Регистрация без оплаты</small></span></label><label className={paid ? 'selected' : ''}><input type="radio" name="payment_mode" disabled={!privileged} checked={paid} onChange={() => setPaid(true)} /><span><strong>Платный билет</strong><small>{privileged ? 'Сбор средств на проведение' : 'Для подтверждённых организаторов'}</small></span></label></fieldset>
      {paid && <><div className="form-two"><label>Цена билета, ₸ *<input name="ticket_price" type="number" min="1" max="1000000" required value={form.ticket_price} onChange={update} /></label><label>Бюджет для проведения, ₸ *<input name="target_budget" type="number" min="1" max="100000000" required value={form.target_budget} onChange={update} /></label></div><div className="editor-budget"><Users size={18} /><span>Для запуска необходимо продать <strong>{minimum} билетов</strong> из {form.capacity || '…'} доступных.</span></div></>}
      <label>Видимость афиши<select name="visibility" disabled={!privileged} value={form.is_private ? 'private' : 'public'} onChange={e => setForm(f => ({ ...f, is_private: e.target.value === 'private' }))}><option value="public">Публичное — в афише и на главной</option><option value="private">Приватное — только по прямой ссылке</option></select></label>{!privileged && <div className="editor-permission"><ShieldCheck size={19} /><p>Ваш аккаунт позволяет создавать бесплатные приватные события. Для публичных афиш и сбора средств <Link to="/support">обратитесь в команду CaspianHub</Link>.</p></div>}
      </div></section>
      <div className="editor-submit"><div><strong>Готово к публикации?</strong><p>Анонс появится со статусом «Идея». Откройте регистрацию в кабинете организатора; для сбора средств добавьте смету и реквизиты.</p></div>{error && <div className="notice error" role="alert">{error}</div>}<button className="btn btn-primary" disabled={busy || uploading}>{busy ? 'Публикуем…' : 'Опубликовать анонс'}<ArrowRight size={18} /></button></div>
    </form>
    <aside className="editor-preview"><span className="section-label">ПРЕДПРОСМОТР АФИШИ</span><div className="editor-preview-card"><div className="editor-preview-art">{form.banner ? <img src={form.banner} alt="Обложка в карточке мероприятия" /> : <><ImagePlus size={32} /><span>Обложка события</span></>}</div><div className="editor-preview-body"><span className="event-status">{form.category}</span><h2>{form.title || 'Название мероприятия'}</h2><p><CalendarDays size={16} />{form.event_date ? new Date(form.event_date).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }) : 'Дата и время'}</p><p><MapPin size={16} />{form.location || 'Площадка проведения'}</p><div><strong>{paid ? priceText(form.ticket_price) : 'Бесплатно'}</strong><span>{form.capacity ? `${form.capacity} мест` : 'Количество мест'}</span></div></div></div><div className="editor-checklist"><h3>Перед публикацией</h3>{[[!!form.banner, 'Загружена обложка'],[form.title.trim().length >= 3 && form.description.trim().length >= 10, 'Добавлены название и программа'],[!!form.event_date && !!form.end_date && !!form.location, 'Указаны даты и площадка']].map(([done,label]) => <div key={label} className={done ? 'done' : ''}><Check size={15} />{label}</div>)}</div><p className="editor-preview-note">Это предпросмотр. Данные сохранятся после публикации.</p></aside>
    </div>
  </main>
}
