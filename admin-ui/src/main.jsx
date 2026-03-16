import React, { useState, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider, theme, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './index.css'

function Root() {
  const [darkMode, setDarkMode] = useState(localStorage.getItem('darkMode') === 'true')
  
  useEffect(() => {
    document.body.style.backgroundColor = darkMode ? '#141414' : '#f0f2f5'
  }, [darkMode])

  const themeConfig = {
    algorithm: darkMode ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      colorPrimary: '#1890ff',
    },
  }

  return (
    <ConfigProvider locale={zhCN} theme={themeConfig}>
      <AntApp>
        <App darkMode={darkMode} setDarkMode={setDarkMode} />
      </AntApp>
    </ConfigProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
)
