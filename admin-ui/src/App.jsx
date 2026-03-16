import React, { useState, useEffect } from 'react'
import { Layout, Menu, theme, Statistic, Card, Row, Col, Table, Tag, Button, Input, Modal, Form, message, Select, Badge, Space } from 'antd'
import { MemoryOutlined, AppstoreOutlined, TeamOutlined, SettingOutlined, PlusOutlined, SearchOutlined, DeleteOutlined, EditOutlined, ApiOutlined } from '@ant-design/icons'
import axios from 'axios'

const { Header, Content, Sider } = Layout
const { Search } = Input

// API 配置
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

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
  return config
})

function App() {
  const [collapsed, setCollapsed] = useState(false)
  const [currentView, setCurrentView] = useState('memories')
  const [apiKey, setApiKey] = useState(localStorage.getItem('apiKey') || '')
  const [instanceInfo, setInstanceInfo] = useState(null)
  const {
    token: { colorBgContainer, borderRadiusLG }
  } = theme.useToken()

  useEffect(() => {
    if (apiKey) {
      fetchInstanceInfo()
    }
  }, [apiKey])

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
    }
  }

  const menuItems = [
    {
      key: 'memories',
      icon: <MemoryOutlined />,
      label: '记忆管理'
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
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', padding: '0 24px', background: '#001529', justifyContent: 'space-between' }}>
        <div style={{ color: '#fff', fontSize: '20px', fontWeight: 'bold' }}>
          <ApiOutlined style={{ marginRight: 8 }} />
          O-Mind 管理面板
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {instanceInfo && (
            <Badge status="success" text={<span style={{ color: '#fff' }}>{instanceInfo.name} ({instanceInfo.instance_id})</span>} />
          )}
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
            {currentView === 'memories' && <MemoriesView api={api} />}
            {currentView === 'agents' && <AgentsView api={api} />}
            {currentView === 'settings' && <SettingsView />}
          </Content>
        </Layout>
      </Layout>
    </Layout>
  )
}

// 记忆管理组件
function MemoriesView({ api }) {
  const [memories, setMemories] = useState([])
  const [loading, setLoading] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [modalVisible, setModalVisible] = useState(false)
  const [editingMemory, setEditingMemory] = useState(null)
  const [form] = Form.useForm()

  const fetchMemories = async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/memories', { params: { limit: 100 } })
      setMemories(res.data)
    } catch (err) {
      message.error('获取记忆失败')
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchMemories()
  }, [])

  const handleSearch = async (value) => {
    setLoading(true)
    try {
      const res = await api.get('/api/memories', { params: { q: value, limit: 100 } })
      setMemories(res.data)
    } catch (err) {
      message.error('搜索失败')
    }
    setLoading(false)
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
      ellipsis: true
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
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
      render: (agent) => agent ? <Tag>{agent}</Tag> : '-'
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date) => new Date(date).toLocaleString('zh-CN')
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)}>删除</Button>
        </Space>
      )
    }
  ]

  return (
    <div style={{ padding: 24 }}>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic title="记忆总数" value={memories.length} prefix={<MemoryOutlined />} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic 
              title="本实例记忆" 
              value={memories.filter(m => m.instance_id).length} 
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
        <Search
          placeholder="搜索记忆内容"
          allowClear
          enterButton={<SearchOutlined />}
          style={{ width: 300 }}
          onSearch={handleSearch}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          新建记忆
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={memories}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
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

// Agent 管理组件
function AgentsView({ api }) {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchAgents = async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/agents')
      // 获取每个Agent的记忆数量
      const agentData = await Promise.all(
        res.data.map(async (agentId) => {
          const memRes = await api.get('/api/memories', { params: { agent_id: agentId, limit: 1000 } })
          return { agentId, count: memRes.data.length }
        })
      )
      setAgents(agentData)
    } catch (err) {
      message.error('获取 Agent 失败')
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchAgents()
  }, [])

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
      <h2>Agent 管理</h2>
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
function SettingsView() {
  const [apiKey, setApiKey] = useState(localStorage.getItem('apiKey') || '')

  const handleSave = () => {
    localStorage.setItem('apiKey', apiKey)
    message.success('设置已保存')
  }

  return (
    <div style={{ padding: 24 }}>
      <h2>设置</h2>
      <Card title="API 配置" style={{ maxWidth: 500 }}>
        <Form layout="vertical">
          <Form.Item label="API Key">
            <Input 
              value={apiKey} 
              onChange={(e) => setApiKey(e.target.value)} 
              placeholder="输入 API Key"
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={handleSave}>保存</Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}

export default App
