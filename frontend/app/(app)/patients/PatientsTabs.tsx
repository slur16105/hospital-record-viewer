'use client'

import { useState } from 'react'
import MyPatientsClient from './MyPatientsClient'
import SearchClient from './SearchClient'
import styles from './PatientsTabs.module.css'

export default function PatientsTabs({ initialTab }: { initialTab: 'my' | 'search' }) {
  const [tab, setTab] = useState<'my' | 'search'>(initialTab)

  return (
    <div>
      <div className={styles.tabBar}>
        <button
          className={tab === 'my' ? `${styles.tab} ${styles.tabActive}` : styles.tab}
          onClick={() => setTab('my')}
        >
          담당 환자
        </button>
        <button
          className={tab === 'search' ? `${styles.tab} ${styles.tabActive}` : styles.tab}
          onClick={() => setTab('search')}
        >
          환자 검색 (신규 진료)
        </button>
      </div>
      {tab === 'my' ? <MyPatientsClient /> : <SearchClient />}
    </div>
  )
}
