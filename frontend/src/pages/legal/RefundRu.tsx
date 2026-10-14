import { Link } from "react-router-dom";
import LegalLayout from "../../components/LegalLayout";
import { LEGAL, legalUpdated, operatorLine } from "../../legal";

const linkClass = "text-iris hover:underline";

export default function RefundRu() {
  return (
    <LegalLayout title="Политика возврата средств" updated={legalUpdated()}>
      <section>
        <h2 className="text-ink-100 text-base mb-3">1. Кто принимает оплату и возвращает средства</h2>
        <p>
          {LEGAL.brand} предоставляет {operatorLine()}. Платные тарифы продаются через Paddle.com Market Ltd (Великобритания), которая выступает продавцом (merchant of record). Paddle принимает оплату, начисляет налоги, где это требуется, и выставляет счета. Номер вашей карты мы никогда не видим. К покупке также применяются условия Paddle для покупателей.
        </p>
        <p className="mt-3">
          Возврат выполняет Paddle на тот же способ оплаты, которым была совершена покупка.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">2. 14 дней на возврат</h2>
        <p>
          Если вы оформили новую подписку Pro, «Школа» или «Университет» онлайн через оплату на{" "}
          <Link to="/pricing" className={linkClass}>странице тарифов</Link>, вы можете запросить полный возврат первого платежа по этой подписке в течение 14 дней после него. Это касается и месячной, и годовой оплаты. Указывать причину не нужно.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">3. Продления и неполные периоды</h2>
        <p>
          Подписки продлеваются автоматически, пока вы их не отмените. Платежи за продление и неиспользованная часть оплаченного периода после первых 14 дней не возвращаются, кроме случаев, когда возврат требует закон.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">4. Отмена</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li>
            Отменить подписку можно в любой момент в платёжном портале (<Link to="/pricing" className={linkClass}>страница тарифов</Link>, кнопка «Управлять»).
          </li>
          <li>После отмены доступ к платному тарифу сохраняется до конца уже оплаченного периода.</li>
          <li>После окончания этого периода подписка не продлевается и деньги больше не списываются.</li>
          <li>
            Запрос на возврат сам по себе не отменяет подписку, а отмена сама по себе не возвращает платёж. Если вам нужно и то и другое, отмените подписку в платёжном портале и напишите нам, как описано в разделе 7.
          </li>
          <li>
            Нельзя удалить аккаунт {LEGAL.brand}, пока действует платная подписка. Сначала отмените её в платёжном портале, чтобы деньги больше не списывались. Удаление аккаунта само по себе не возвращает платёж.
          </li>
        </ul>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">5. Смена тарифа</h2>
        <p>
          Переход с платного тарифа на бесплатный считается отменой и регулируется разделом 4. Смена одного платного тарифа на другой или переход между месячной и годовой оплатой в существующей подписке не является новой подпиской и не открывает новый 14-дневный срок возврата. С вопросами о смене тарифа пишите на{" "}
          <a href={`mailto:${LEGAL.emails.finance}`} className={linkClass}>{LEGAL.emails.finance}</a>.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">6. Корпоративные клиенты и клиенты по договору</h2>
        <p>
          Если ваша организация платит по подписанному соглашению или корпоративному договору, возврат регулируется условиями этого договора, а не этой политикой.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">7. Как запросить возврат</h2>
        <p>
          Напишите на <a href={`mailto:${LEGAL.emails.finance}`} className={linkClass}>{LEGAL.emails.finance}</a> и укажите:
        </p>
        <ul className="list-disc list-inside space-y-1 mt-2 text-ink-400">
          <li>адрес почты вашего аккаунта {LEGAL.brand};</li>
          <li>ваш тариф и период оплаты (месяц или год);</li>
          <li>номер заказа или счёта Paddle, если он у вас есть.</li>
        </ul>
        <p className="mt-3">
          Мы отвечаем на запросы о возврате в течение 30 дней. Когда Paddle выполнит возврат, срок зачисления зависит от вашего банка или эмитента карты.
        </p>
        <p className="mt-3">
          Наша <Link to="/privacy" className={linkClass}>Политика конфиденциальности</Link> объясняет, как мы обращаемся с персональными данными в вашем запросе.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">8. Ваши права по закону</h2>
        <p>
          Ничто в этой политике не ограничивает ваши права по законодательству о защите потребителей вашей страны. Если вы потребитель в Европейском союзе или Великобритании, ваше законное право на отказ от покупки этой политикой не ограничивается.
        </p>
      </section>

      <section>
        <h2 className="text-ink-100 text-base mb-3">9. Контакты</h2>
        <ul className="list-disc list-inside space-y-1 text-ink-400">
          <li>
            Возвраты и счета:{" "}
            <a href={`mailto:${LEGAL.emails.finance}`} className={linkClass}>{LEGAL.emails.finance}</a>
          </li>
          <li>
            Корпоративный тариф и договоры:{" "}
            <a href={`mailto:${LEGAL.emails.sales}`} className={linkClass}>{LEGAL.emails.sales}</a>
          </li>
          <li>
            Другие вопросы:{" "}
            <a href={`mailto:${LEGAL.emails.support}`} className={linkClass}>{LEGAL.emails.support}</a>
          </li>
        </ul>
      </section>
    </LegalLayout>
  );
}
