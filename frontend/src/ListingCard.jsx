import { Link } from 'react-router-dom'
import { MapPin, Package } from 'lucide-react'

export const priceText = value => Number(value) > 0 ? `${new Intl.NumberFormat('ru-RU').format(value)} ₸` : 'Бесплатно'
export function ListingCard({ item }) {
  return <Link to={`/market/${item.id}`} className="item-card market-card">
    <div className="item-photo">{item.image ? <img src={item.image} alt={item.title} loading="lazy" /> : <div className="image-fallback"><Package size={42} /></div>}{!item.price && <span className="free-badge">Отдают бесплатно</span>}</div>
    <div className="item-body"><div className="item-kicker"><span>{item.category}</span><span>{new Date(item.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}</span></div><strong className="market-price">{priceText(item.price)}</strong><h3>{item.title}</h3><div className="item-meta"><MapPin size={14} />{item.location}</div></div>
  </Link>
}
