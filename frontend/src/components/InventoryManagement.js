import React, { useState, useEffect } from 'react';
import axios from 'axios';

const InventoryManagement = () => {
  const [bags, setBags] = useState([]);
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    bag_id: '',
    production_date: '',
    expiry_date: '',
    weight: '50',
    quality_score: '100',
    cluster_id: ''
  });
  const [filter, setFilter] = useState({
    cluster: 'all',
    status: 'all',
    sort: 'date-asc'
  });
  const [selectedBag, setSelectedBag] = useState(null);

  useEffect(() => {
    // In a real application, we would fetch data from the API
    const fetchData = async () => {
      try {
        setLoading(true);
        // For now, start with empty arrays to let the user add their own data
        setBags([]);
        setClusters([]);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching data:', error);
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Create a new bag with an ID
    const newBag = {
      id: bags.length > 0 ? Math.max(...bags.map(b => b.id)) + 1 : 1,
      ...formData,
      status: 'in_stock',
      arrival_date: new Date().toISOString().split('T')[0],
      days_in_storage: 0
    };
    
    // Convert string values to appropriate types
    newBag.weight = parseFloat(newBag.weight);
    newBag.quality_score = parseInt(newBag.quality_score);
    newBag.cluster_id = parseInt(newBag.cluster_id);
    
    // Find the cluster name for display
    const selectedCluster = clusters.find(c => c.id === newBag.cluster_id);
    newBag.cluster_name = selectedCluster ? selectedCluster.name : 'Unknown';
    
    setBags([...bags, newBag]);
    setShowForm(false);
    setFormData({
      bag_id: '',
      production_date: '',
      expiry_date: '',
      weight: '50',
      quality_score: '100',
      cluster_id: ''
    });
  };

  const handleEditBag = (bag) => {
    setSelectedBag(bag);
    setFormData({
      bag_id: bag.bag_id,
      production_date: bag.production_date,
      expiry_date: bag.expiry_date,
      weight: bag.weight.toString(),
      quality_score: bag.quality_score.toString(),
      cluster_id: bag.cluster_id.toString()
    });
    setShowForm(true);
  };

  const handleUpdateBag = (e) => {
    e.preventDefault();
    
    if (!selectedBag) return;
    
    // Update the selected bag
    const updatedBag = {
      ...selectedBag,
      ...formData
    };
    
    // Convert string values to appropriate types
    updatedBag.weight = parseFloat(updatedBag.weight);
    updatedBag.quality_score = parseInt(updatedBag.quality_score);
    updatedBag.cluster_id = parseInt(updatedBag.cluster_id);
    
    // Find the cluster name for display
    const selectedCluster = clusters.find(c => c.id === updatedBag.cluster_id);
    updatedBag.cluster_name = selectedCluster ? selectedCluster.name : 'Unknown';
    
    // Update bags array
    const updatedBags = bags.map(bag => 
      bag.id === selectedBag.id ? updatedBag : bag
    );
    
    setBags(updatedBags);
    setShowForm(false);
    setSelectedBag(null);
    setFormData({
      bag_id: '',
      production_date: '',
      expiry_date: '',
      weight: '50',
      quality_score: '100',
      cluster_id: ''
    });
  };

  const handleAddCluster = () => {
    // This is a simplified version for demonstration
    const clusterName = prompt('Enter cluster name:');
    if (clusterName) {
      const newCluster = {
        id: clusters.length > 0 ? Math.max(...clusters.map(c => c.id)) + 1 : 1,
        name: clusterName,
        location_x: 0,
        location_y: 0,
        length: 5,
        width: 5,
        max_capacity: 100,
        current_count: 0,
        utilization_percentage: 0
      };
      setClusters([...clusters, newCluster]);
    }
  };

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilter({
      ...filter,
      [name]: value
    });
  };

  const handleStatusChange = (bagId, newStatus) => {
    const updatedBags = bags.map(bag => {
      if (bag.id === bagId) {
        return { ...bag, status: newStatus };
      }
      return bag;
    });
    setBags(updatedBags);
  };

  const getFilteredBags = () => {
    let filtered = [...bags];
    
    // Apply cluster filter
    if (filter.cluster !== 'all') {
      filtered = filtered.filter(bag => bag.cluster_id.toString() === filter.cluster);
    }
    
    // Apply status filter
    if (filter.status !== 'all') {
      filtered = filtered.filter(bag => bag.status === filter.status);
    }
    
    // Apply sorting
    switch (filter.sort) {
      case 'date-asc':
        filtered.sort((a, b) => new Date(a.production_date) - new Date(b.production_date));
        break;
      case 'date-desc':
        filtered.sort((a, b) => new Date(b.production_date) - new Date(a.production_date));
        break;
      case 'expiry-asc':
        filtered.sort((a, b) => new Date(a.expiry_date) - new Date(b.expiry_date));
        break;
      case 'expiry-desc':
        filtered.sort((a, b) => new Date(b.expiry_date) - new Date(a.expiry_date));
        break;
      case 'quality-asc':
        filtered.sort((a, b) => a.quality_score - b.quality_score);
        break;
      case 'quality-desc':
        filtered.sort((a, b) => b.quality_score - a.quality_score);
        break;
      default:
        break;
    }
    
    return filtered;
  };

  const getStatusClass = (status) => {
    switch (status) {
      case 'in_stock':
        return 'status-in-stock';
      case 'shipped':
        return 'status-shipped';
      case 'expired':
        return 'status-expired';
      case 'damaged':
        return 'status-damaged';
      default:
        return '';
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'in_stock':
        return 'In Stock';
      case 'shipped':
        return 'Shipped';
      case 'expired':
        return 'Expired';
      case 'damaged':
        return 'Damaged';
      default:
        return status;
    }
  };

  const getQualityClass = (score) => {
    if (score >= 90) return 'quality-high';
    if (score >= 70) return 'quality-medium';
    return 'quality-low';
  };

  if (loading) {
    return <div className="loading">Loading inventory data...</div>;
  }

  const filteredBags = getFilteredBags();

  return (
    <div className="inventory-management">
      <h2>Inventory Management</h2>
      <p className="page-description">Track and manage cement bags across all storage clusters</p>

      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Cement Bag Inventory</h3>
          <div className="card-actions">
            {clusters.length === 0 && (
              <button 
                className="btn btn-secondary" 
                onClick={handleAddCluster}
              >
                Add Cluster
              </button>
            )}
            <button 
              className="btn btn-primary" 
              onClick={() => {
                setShowForm(!showForm);
                setSelectedBag(null);
                setFormData({
                  bag_id: '',
                  production_date: '',
                  expiry_date: '',
                  weight: '50',
                  quality_score: '100',
                  cluster_id: ''
                });
              }}
              disabled={clusters.length === 0}
            >
              {showForm ? 'Cancel' : 'Add Bag'}
            </button>
          </div>
        </div>

        {showForm && (
          <div className="bag-form">
            <h4>{selectedBag ? 'Edit Cement Bag' : 'Add New Cement Bag'}</h4>
            <form onSubmit={selectedBag ? handleUpdateBag : handleSubmit}>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Bag ID</label>
                  <input
                    type="text"
                    name="bag_id"
                    className="form-control"
                    value={formData.bag_id}
                    onChange={handleInputChange}
                    placeholder="e.g., JSW-12345"
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Cluster</label>
                  <select
                    name="cluster_id"
                    className="form-control"
                    value={formData.cluster_id}
                    onChange={handleInputChange}
                    required
                  >
                    <option value="">Select Cluster</option>
                    {clusters.map(cluster => (
                      <option key={cluster.id} value={cluster.id}>
                        {cluster.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Production Date</label>
                  <input
                    type="date"
                    name="production_date"
                    className="form-control"
                    value={formData.production_date}
                    onChange={handleInputChange}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Expiry Date</label>
                  <input
                    type="date"
                    name="expiry_date"
                    className="form-control"
                    value={formData.expiry_date}
                    onChange={handleInputChange}
                    required
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Weight (kg)</label>
                  <input
                    type="number"
                    name="weight"
                    className="form-control"
                    value={formData.weight}
                    onChange={handleInputChange}
                    step="0.1"
                    min="0.1"
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Quality Score (0-100)</label>
                  <input
                    type="number"
                    name="quality_score"
                    className="form-control"
                    value={formData.quality_score}
                    onChange={handleInputChange}
                    min="0"
                    max="100"
                    required
                  />
                </div>
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary">
                  {selectedBag ? 'Update Bag' : 'Save Bag'}
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="filter-controls">
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Cluster</label>
              <select
                name="cluster"
                className="form-control"
                value={filter.cluster}
                onChange={handleFilterChange}
              >
                <option value="all">All Clusters</option>
                {clusters.map(cluster => (
                  <option key={cluster.id} value={cluster.id.toString()}>
                    {cluster.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Status</label>
              <select
                name="status"
                className="form-control"
                value={filter.status}
                onChange={handleFilterChange}
              >
                <option value="all">All Statuses</option>
                <option value="in_stock">In Stock</option>
                <option value="shipped">Shipped</option>
                <option value="expired">Expired</option>
                <option value="damaged">Damaged</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Sort By</label>
              <select
                name="sort"
                className="form-control"
                value={filter.sort}
                onChange={handleFilterChange}
              >
                <option value="date-asc">Production Date (Oldest First)</option>
                <option value="date-desc">Production Date (Newest First)</option>
                <option value="expiry-asc">Expiry Date (Soonest First)</option>
                <option value="expiry-desc">Expiry Date (Latest First)</option>
                <option value="quality-asc">Quality Score (Low to High)</option>
                <option value="quality-desc">Quality Score (High to Low)</option>
              </select>
            </div>
          </div>
        </div>

        {clusters.length === 0 ? (
          <div className="no-data">
            <span className="material-icons">inventory_2</span>
            <p>No clusters defined yet</p>
            <p>Add a cluster first before adding cement bags</p>
          </div>
        ) : bags.length === 0 ? (
          <div className="no-data">
            <span className="material-icons">inventory_2</span>
            <p>No cement bags in inventory</p>
            <p>Click "Add Bag" to add cement bags to your inventory</p>
          </div>
        ) : filteredBags.length === 0 ? (
          <div className="no-data">
            <span className="material-icons">filter_alt</span>
            <p>No bags match the current filters</p>
            <p>Try adjusting your filter criteria</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Bag ID</th>
                <th>Cluster</th>
                <th>Production Date</th>
                <th>Expiry Date</th>
                <th>Days in Storage</th>
                <th>Weight (kg)</th>
                <th>Quality</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredBags.map(bag => (
                <tr key={bag.id}>
                  <td>{bag.bag_id}</td>
                  <td>{bag.cluster_name}</td>
                  <td>{bag.production_date}</td>
                  <td>{bag.expiry_date}</td>
                  <td>{bag.days_in_storage}</td>
                  <td>{bag.weight}</td>
                  <td>
                    <div className={`quality-indicator ${getQualityClass(bag.quality_score)}`}>
                      {bag.quality_score}%
                    </div>
                  </td>
                  <td>
                    <span className={`status-badge ${getStatusClass(bag.status)}`}>
                      {getStatusLabel(bag.status)}
                    </span>
                  </td>
                  <td>
                    <div className="button-group">
                      <button 
                        className="btn btn-sm btn-secondary"
                        onClick={() => handleEditBag(bag)}
                      >
                        Edit
                      </button>
                      <div className="status-actions">
                        <select
                          className="form-control form-control-sm"
                          value={bag.status}
                          onChange={(e) => handleStatusChange(bag.id, e.target.value)}
                        >
                          <option value="in_stock">Mark as In Stock</option>
                          <option value="shipped">Mark as Shipped</option>
                          <option value="expired">Mark as Expired</option>
                          <option value="damaged">Mark as Damaged</option>
                        </select>
                      </div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Inventory Overview</h3>
        </div>
        {bags.length === 0 ? (
          <div className="no-data">
            <span className="material-icons">analytics</span>
            <p>Add bags to see inventory statistics</p>
          </div>
        ) : (
          <div className="inventory-stats">
            <div className="stat-item">
              <h4>Total Bags</h4>
              <p className="stat-value">{bags.length}</p>
            </div>
            <div className="stat-item">
              <h4>In Stock</h4>
              <p className="stat-value">
                {bags.filter(bag => bag.status === 'in_stock').length}
              </p>
            </div>
            <div className="stat-item">
              <h4>Shipped</h4>
              <p className="stat-value">
                {bags.filter(bag => bag.status === 'shipped').length}
              </p>
            </div>
            <div className="stat-item">
              <h4>Expired</h4>
              <p className="stat-value">
                {bags.filter(bag => bag.status === 'expired').length}
              </p>
            </div>
            <div className="stat-item">
              <h4>Damaged</h4>
              <p className="stat-value">
                {bags.filter(bag => bag.status === 'damaged').length}
              </p>
            </div>
            <div className="stat-item">
              <h4>Average Quality</h4>
              <p className="stat-value">
                {bags.length > 0 
                  ? (bags.reduce((sum, bag) => sum + bag.quality_score, 0) / bags.length).toFixed(1) + '%'
                  : 'N/A'
                }
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default InventoryManagement;
