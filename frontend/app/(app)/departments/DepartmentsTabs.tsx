'use client'

import { useState } from 'react'
import DepartmentsClient from './DepartmentsClient'
import RoomsClient from './RoomsClient'
import styles from './DepartmentsTabs.module.css'

export default function DepartmentsTabs({
  initialTab,
}: {
  initialTab: 'departments' | 'rooms'
}) {
  const [tab, setTab] = useState<'departments' | 'rooms'>(initialTab)

  return (
    <div>
      <div className={styles.tabBar}>
        <button
          className={tab === 'departments' ? `${styles.tab} ${styles.tabActive}` : styles.tab}
          onClick={() => setTab('departments')}
        >
          진료과목
        </button>
        <button
          className={tab === 'rooms' ? `${styles.tab} ${styles.tabActive}` : styles.tab}
          onClick={() => setTab('rooms')}
        >
          진료실
        </button>
      </div>
      {tab === 'departments' ? <DepartmentsClient /> : <RoomsClient />}
    </div>
  )
}
