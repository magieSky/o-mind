import React, { useState, useEffect } from 'react'
import { Layout, Menu, theme, Statistic, Card, Row, Col, Table, Tag, Button, Input, Modal, Form, message, Select, Badge, Space, Switch, Checkbox, Popconfirm, Typography, Timeline } from 'antd'
import { InboxOutlined, AppstoreOutlined, TeamOutlined, SettingOutlined, PlusOutlined, SearchOutlined, DeleteOutlined, EditOutlined, ApiOutlined, ExportOutlined, ImportOutlined, BarChartOutlined, SunOutlined, MoonOutlined, DeleteFilled } from '@ant-design/icons'
import axios from 'axios'

const { Header, Content, Sider } = Layout
const { Search } = Input
const { Title } = Typography

// API 配置 - 使用相对路径，通过 nginx 代理
const API_BASE = ''

// 创建 axios 实例
const api = axios.create({
  baseURL: API_BASE,
  timeout: 10000
})

// 添加 API Key 到请求头
api.interceptors.request.use(config => {
  const apiKey = localStorage.getItem('apiKey') || ''
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey
  }
  // 添加时间戳防止缓存
  config.params = { ...config.params, _t: Date.now() }
  return config
})

function App({ darkMode: propDarkMode, setDarkMode: propSetDarkMode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [currentView, setCurrentView] = useState('memories')
  const [apiKey, setApiKey] = useState(localStorage.getItem('apiKey') || '')
  const [instanceInfo, setInstanceInfo] = useState(null)
  const [darkModeLocal, setDarkModeLocal] = useState(localStorage.getItem('darkMode') === 'true')

  // 使用 props 或者本地状态
  const darkMode = propDarkMode !== undefined ? propDarkMode : darkModeLocal
  const setDarkMode = propSetDarkMode || setDarkModeLocal

  const {
    token: { colorBgContainer, borderRadiusLG }
  } = theme.useToken()

  useEffect(() => {
    if (apiKey) {
      fetchInstanceInfo()
      // 注意：memories 和 stats 在各自的组件中通过 useEffect 获取
    }
  }, [apiKey])

  useEffect(() => {
    document.body.style.backgroundColor = darkMode ? '#141414' : '#f0f2f5'
  }, [darkMode])

  const fetchInstanceInfo = async () => {
    try {
      const res = await api.get('/api/instances/info')
      setInstanceInfo(res.data)
    } catch (err) {
      console.error('Failed to fetch instance info:', err)
    }
  }

  const handleApiKeyChange = (value) => {
    setApiKey(value)
    localStorage.setItem('apiKey', value)
    if (value) {
      fetchInstanceInfo()
      // 强制刷新页面
      window.location.reload()
    }
  }

  const toggleDarkMode = (checked) => {
    setDarkMode(checked)
    localStorage.setItem('darkMode', checked)
  }

  const menuItems = [
    {
      key: 'memories',
      icon: <InboxOutlined />,
      label: '记忆管理'
    },
    {
      key: 'stats',
      icon: <BarChartOutlined />,
      label: '数据统计'
    },
    {
      key: 'agents',
      icon: <TeamOutlined />,
      label: 'Agent 管理'
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '设置'
    }
  ]

  return (
    <Layout style={{ minHeight: '100vh', background: darkMode ? '#141414' : '#f0f2f5' }}>
      <Header style={{ display: 'flex', alignItems: 'center', padding: '0 24px', background: darkMode ? '#1f1f1f' : '#001529', justifyContent: 'space-between' }}>
        <div style={{ color: '#fff', fontSize: '20px', fontWeight: 'bold' }}>
          <ApiOutlined style={{ marginRight: 8 }} />
          O-Mind 管理面板
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {instanceInfo && (
            <Badge status="success" text={<span style={{ color: '#fff' }}>{instanceInfo.name} ({instanceInfo.instance_id})</span>} />
          )}
          <Switch
            checked={darkMode}
            onChange={toggleDarkMode}
            checkedChildren={<MoonOutlined />}
            unCheckedChildren={<SunOutlined />}
          />
          <Select
            value={apiKey}
            onChange={handleApiKeyChange}
            style={{ width: 200 }}
            placeholder="选择 API Key"
            allowClear
          >
            <Select.Option value="key-prod-1">key-prod-1 (prod-1)</Select.Option>
            <Select.Option value="key-test-1">key-test-1 (test-1)</Select.Option>
          </Select>
        </div>
      </Header>
      <Layout>
        <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} style={{ background: colorBgContainer }}>
          <Menu
            mode="inline"
            selectedKeys={[currentView]}
            onClick={(e) => setCurrentView(e.key)}
            items={menuItems}
            style={{ height: '100%', borderRight: 0 }}
          />
        </Sider>
        <Layout style={{ padding: '24px' }}>
          <Content
            style={{
              background: colorBgContainer,
              borderRadius: borderRadiusLG,
              minHeight: 280
            }}
          >
            {currentView === 'memories' && <MemoriesView api={api} apiKey={apiKey} darkMode={darkMode} />}
            {currentView === 'stats' && <StatsView api={api} apiKey={apiKey} darkMode={darkMode} />}
            {currentView === 'agents' && <AgentsView api={api} apiKey={apiKey} darkMode={darkMode} />}
            {currentView === 'settings' && <SettingsView darkMode={darkMode} />}
          </Content>
        </Layout>
      </Layout>
    </Layout>
  )
}

// 记忆管理组件
function MemoriesView({ api, apiKey, darkMode }) {
  const [memories, setMemories] = useState([])
  const [loading, setLoading] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [modalVisible, setModalVisible] = useState(false)
  const [editingMemory, setEditingMemory] = useState(null)
  const [selectedRowKeys, setSelectedRowKeys] = useState([])
  const [form] = Form.useForm()
  const [searchKeyword, setSearchKeyword] = useState('')
  const [pagination, setPagination] = useState({ total: 0, current: 1, pageSize: 10 })
  
  const fetchMemories = async (page = 1) => {
    setLoading(true)
    try {
      const res = await api.get('/api/memories/list', {
        params: {
          page: page,
          page_size: 10,
          q: searchKeyword
        }
      })
      setMemories(res.data.items)
      setPagination({ ...pagination, total: res.data.total, current: res.data.page })
    } catch (err) {
      message.error('获取记忆失败')
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchMemories()
  }, [apiKey])

  const handleSearch = async (value) => {
    setSearchKeyword(value)
    setLoading(true)
    try {
      const res = await api.get('/api/memories/list', {
        params: {
          page: 1,
          page_size: 100,
          q: value
        }
      })
      setMemories(res.data.items)
      setPagination({ ...pagination, total: res.data.total, current: 1 })
    } catch (err) {
      message.error('搜索失败')
    }
    setLoading(false)
  }

  const handlePageChange = (page) => {
    fetchMemories(page)
  }

  const handleAdd = () => {
    setEditingMemory(null)
    form.resetFields()
    setModalVisible(true)
  }

  const handleEdit = (record) => {
    setEditingMemory(record)
    form.setFieldsValue(record)
    setModalVisible(true)
  }

  const handleDelete = async (id) => {
    try {
      await api.delete(`/api/memories/${id}`)
      message.success('删除成功')
      fetchMemories()
    } catch (err) {
      message.error('删除失败')
    }
  }

  const handleBatchDelete = async () => {
    try {
      await api.post('/api/memories/batch-delete', selectedRowKeys)
      message.success(`成功删除 ${selectedRowKeys.length} 条记忆`)
      setSelectedRowKeys([])
      fetchMemories()
    } catch (err) {
      message.error('批量删除失败')
    }
  }

  const handleExport = async () => {
    try {
      const res = await api.get('/api/memories/export')
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `o-mind-memories-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
      message.success('导出成功')
    } catch (err) {
      message.error('导出失败')
    }
  }

  const handleImport = () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.json'
    input.onchange = async (e) => {
      const file = e.target.files[0]
      if (!file) return

      try {
        const text = await file.text()
        const data = JSON.parse(text)
        await api.post('/api/memories/import', data)
        message.success('导入成功')
        fetchMemories()
      } catch (err) {
        message.error('导入失败，请检查文件格式')
      }
    }
    input.click()
  }

  const handleSubmit = async (values) => {
    try {
      if (editingMemory) {
        await api.put(`/api/memories/${editingMemory.id}`, values)
        message.success('更新成功')
      } else {
        await api.post('/api/memories', values)
        message.success('创建成功')
      }
      setModalVisible(false)
      fetchMemories()
    } catch (err) {
      message.error('操作失败')
    }
  }

  const columns = [
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      width: '35%',
      ellipsis: true
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: '15%',
      render: (tags) => (
        <>
          {tags?.map(tag => <Tag key={tag} color="blue">{tag}</Tag>)}
        </>
      )
    },
    {
      title: 'Agent',
      dataIndex: 'agent_id',
      key: 'agent_id',
      width: '15%',
      ellipsis: true,
      render: (agent) => agent ? <Tag>{agent.length > 20 ? agent.slice(0, 20) + '...' : agent}</Tag> : '-'
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: '15%',
      render: (date) => new Date(date).toLocaleString('zh-CN')
    },
    {
      title: '操作',
      key: 'action',
      width: '15%',
      render: (_, record) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)}>删除</Button>
        </Space>
      )
    }
  ]

  const rowSelection = {
    selectedRowKeys,
    onChange: setSelectedRowKeys
  }

  return (
    <div style={{ padding: 24 }}>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic title="记忆总数" value={pagination.total} prefix={<InboxOutlined />} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="本实例记忆"
              value={pagination.total}
              prefix={<AppstoreOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Agent 数量"
              value={new Set(memories.map(m => m.agent_id).filter(Boolean)).size}
              prefix={<TeamOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Space>
          <Search
            placeholder="搜索记忆内容"
            allowClear
            enterButton={<SearchOutlined />}
            style={{ width: 300 }}
            onSearch={handleSearch}
          />
        </Space>
        <Space>
          {selectedRowKeys.length > 0 && (
            <Popconfirm
              title={`确定删除这 ${selectedRowKeys.length} 条记忆吗？`}
              onConfirm={handleBatchDelete}
            >
              <Button danger icon={<DeleteFilled />}>
                批量删除 ({selectedRowKeys.length})
              </Button>
            </Popconfirm>
          )}
          <Button icon={<ExportOutlined />} onClick={handleExport}>导出</Button>
          <Button icon={<ImportOutlined />} onClick={handleImport}>导入</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            新建记忆
          </Button>
        </Space>
      </div>

      <Table
        rowSelection={rowSelection}
        columns={columns}
        dataSource={memories}
        rowKey="id"
        loading={loading}
        pagination={{ 
          pageSize: 10, 
          total: pagination.total,
          current: pagination.current,
          onChange: handlePageChange,
          showSizeChanger: false
        }}
      />

      <Modal
        title={editingMemory ? '编辑记忆' : '新建记忆'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="content" label="内容" rules={[{ required: true }]}>
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select mode="tags" placeholder="输入标签后回车" />
          </Form.Item>
          <Form.Item name="agent_id" label="Agent ID">
            <Input placeholder="可选" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

// 统计组件
function StatsView({ api, apiKey, darkMode }) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)

  const fetchStats = async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/stats')
      setStats(res.data)
    } catch (err) {
      message.error('获取统计失败')
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchStats()
  }, [apiKey])

  const tagData = stats ? Object.entries(stats.tag_counts || {}).map(([name, value]) => ({ name, value })) : []

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>数据统计</Title>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic title="记忆总数" value={stats?.total_memories || 0} prefix={<InboxOutlined />} valueStyle={{ color: '#1890ff' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="Agent 数量" value={stats?.total_agents || 0} prefix={<TeamOutlined />} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="标签种类" value={tagData.length} prefix={<AppstoreOutlined />} valueStyle={{ color: '#722ed1' }} />
          </Card>
        </Col>
      </Row>

      <Card title="标签分布" style={{ marginBottom: 24 }}>
        {tagData.length > 0 ? (
          <div style={{ maxHeight: 400, overflow: 'auto' }}>
            {tagData.sort((a, b) => b.value - a.value).map((tag, index) => (
              <div key={tag.name} style={{ marginBottom: 8, display: 'flex', alignItems: 'center' }}>
                <Tag color="blue" style={{ minWidth: 80 }}>{tag.name}</Tag>
                <div style={{ flex: 1, marginLeft: 16 }}>
                  <div style={{
                    width: `${(tag.value / tagData[0].value) * 100}%`,
                    height: 20,
                    background: darkMode ? '#1890ff' : '#1890ff',
                    borderRadius: 4,
                    minWidth: 20
                  }} />
                </div>
                <span style={{ marginLeft: 16, minWidth: 30 }}>{tag.value}</span>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ textAlign: 'center', color: '#999' }}>暂无数据</div>
        )}
      </Card>

      <Card title="最近活动">
        <Timeline
          items={[
            { children: '系统运行中', color: 'green' },
            { children: '等待新记忆...', color: 'gray' }
          ]}
        />
      </Card>
    </div>
  )
}

// Agent 管理组件
function AgentsView({ api, apiKey, darkMode }) {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchAgents = async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/agents')
      // 获取每个Agent的记忆数量
      const agentData = await Promise.all(
        res.data.map(async (agentId) => {
          try {
            const memRes = await api.get('/api/memories', { params: { agent_id: agentId, limit: 1000 } })
            return { agentId, count: memRes.data.length }
          } catch {
            return { agentId, count: 0 }
          }
        })
      )
      setAgents(agentData)
    } catch (err) {
      console.error('Failed to fetch agents:', err)
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchAgents()
  }, [apiKey])

  const columns = [
    {
      title: 'Agent ID',
      dataIndex: 'agentId',
      key: 'agentId'
    },
    {
      title: '记忆数量',
      dataIndex: 'count',
      key: 'count',
      render: (count) => <Badge count={count} showZero color="blue" />
    }
  ]

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>Agent 管理</Title>
      <Table
        columns={columns}
        dataSource={agents}
        rowKey="agentId"
        loading={loading}
        pagination={false}
      />
    </div>
  )
}

// 设置组件
function SettingsView({ darkMode }) {
  const [apiKey, setApiKey] = useState(localStorage.getItem('apiKey') || '')
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    localStorage.setItem('apiKey', apiKey)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>设置</Title>
      <Card title="基本设置" style={{ maxWidth: 500 }}>
        <Form layout="vertical">
          <Form.Item label="API Key">
            <Input
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="输入 API Key"
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={handleSave}>
              {saved ? '已保存 ✓' : '保存'}
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}

export default App
