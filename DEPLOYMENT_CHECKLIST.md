# Deployment Checklist - Research Dataset Builder

Use this checklist to ensure a secure and successful deployment.

## Pre-Deployment

### Security Configuration

- [ ] **Change all default passwords**
  - [ ] Database passwords
  - [ ] Default user passwords (admin, researcher)
  - [ ] JWT secret key

- [ ] **Configure environment variables**
  - [ ] Set strong JWT_SECRET_KEY (min 32 characters)
  - [ ] Set production database credentials
  - [ ] Set LLM API keys (OpenAI or Anthropic)
  - [ ] Set FHIR endpoint URLs and tokens
  - [ ] Set APP_ENV=production

- [ ] **Enable encryption**
  - [ ] Configure PostgreSQL encryption at rest (AES-256)
  - [ ] Configure DuckDB encryption
  - [ ] Set up TLS 1.3 for API endpoints
  - [ ] Configure HTTPS with valid SSL certificates
  - [ ] Set up AWS KMS or Azure Key Vault for key management

- [ ] **Configure CORS**
  - [ ] Update allowed origins in main.py
  - [ ] Remove wildcard (*) origins
  - [ ] Add only trusted frontend domains

- [ ] **Set up rate limiting**
  - [ ] Install slowapi or similar
  - [ ] Configure per-endpoint rate limits
  - [ ] Set up IP-based throttling

### Database Setup

- [ ] **PostgreSQL configuration**
  - [ ] Create production database
  - [ ] Set up connection pooling
  - [ ] Configure backup strategy
  - [ ] Set up replication (if needed)
  - [ ] Create database indexes
  - [ ] Configure max connections

- [ ] **DuckDB configuration**
  - [ ] Set up persistent storage
  - [ ] Configure backup strategy
  - [ ] Set memory limits

- [ ] **Run migrations**
  - [ ] Initialize database schema
  - [ ] Create initial admin user
  - [ ] Verify all tables created
  - [ ] Check foreign key constraints

### Application Configuration

- [ ] **Logging**
  - [ ] Configure production log level (INFO or WARNING)
  - [ ] Set up log rotation
  - [ ] Configure log aggregation (e.g., CloudWatch, Datadog)
  - [ ] Set up error tracking (e.g., Sentry)

- [ ] **Monitoring**
  - [ ] Set up health check monitoring
  - [ ] Configure uptime monitoring
  - [ ] Set up performance monitoring (APM)
  - [ ] Configure database monitoring
  - [ ] Set up alerts for errors and downtime

- [ ] **Backup**
  - [ ] Configure automated database backups
  - [ ] Test backup restoration
  - [ ] Set up backup retention policy (7 years for audit logs)
  - [ ] Configure off-site backup storage

### Testing

- [ ] **Functional testing**
  - [ ] Test authentication flow
  - [ ] Test query submission
  - [ ] Test dataset generation
  - [ ] Test export functionality
  - [ ] Test FHIR integration
  - [ ] Test error handling

- [ ] **Security testing**
  - [ ] Run security scan (e.g., OWASP ZAP)
  - [ ] Test SQL injection protection
  - [ ] Test authentication bypass attempts
  - [ ] Test authorization enforcement
  - [ ] Verify audit logging

- [ ] **Performance testing**
  - [ ] Load test with expected user volume
  - [ ] Test query execution times
  - [ ] Test concurrent user handling
  - [ ] Test large dataset generation
  - [ ] Identify and fix bottlenecks

- [ ] **Integration testing**
  - [ ] Test end-to-end query flow
  - [ ] Test FHIR data ingestion
  - [ ] Test multi-source dataset assembly
  - [ ] Test export in all formats

## Deployment

### Infrastructure

- [ ] **Server setup**
  - [ ] Provision production servers
  - [ ] Configure firewall rules
  - [ ] Set up load balancer (if needed)
  - [ ] Configure auto-scaling (if needed)
  - [ ] Set up CDN for static assets

- [ ] **Container orchestration** (if using Docker)
  - [ ] Set up Kubernetes or ECS
  - [ ] Configure container registry
  - [ ] Set up secrets management
  - [ ] Configure resource limits
  - [ ] Set up health checks

- [ ] **Network configuration**
  - [ ] Configure VPC/network isolation
  - [ ] Set up private subnets for databases
  - [ ] Configure security groups
  - [ ] Set up VPN access for admins
  - [ ] Configure DNS records

### Application Deployment

- [ ] **Build and deploy**
  - [ ] Build Docker images
  - [ ] Push to container registry
  - [ ] Deploy to production environment
  - [ ] Run database migrations
  - [ ] Verify deployment success

- [ ] **Configuration**
  - [ ] Verify environment variables
  - [ ] Check database connections
  - [ ] Verify LLM API connectivity
  - [ ] Test FHIR endpoint connectivity
  - [ ] Verify file storage access

- [ ] **Frontend deployment** (when ready)
  - [ ] Build production frontend
  - [ ] Deploy to hosting (Vercel, Netlify, or S3+CloudFront)
  - [ ] Configure API endpoint URLs
  - [ ] Verify CORS configuration
  - [ ] Test frontend-backend integration

## Post-Deployment

### Verification

- [ ] **Smoke tests**
  - [ ] Health check endpoint responds
  - [ ] Login works
  - [ ] Query submission works
  - [ ] Dataset generation works
  - [ ] Export works
  - [ ] Audit logs are created

- [ ] **Monitoring verification**
  - [ ] Logs are being collected
  - [ ] Metrics are being reported
  - [ ] Alerts are configured
  - [ ] Error tracking is working

- [ ] **Security verification**
  - [ ] HTTPS is enforced
  - [ ] Authentication is required
  - [ ] Authorization is enforced
  - [ ] Audit logs are immutable
  - [ ] Sensitive data is encrypted

### Documentation

- [ ] **User documentation**
  - [ ] Create user guide
  - [ ] Document API endpoints
  - [ ] Create query examples
  - [ ] Document data sources
  - [ ] Create troubleshooting guide

- [ ] **Admin documentation**
  - [ ] Document deployment process
  - [ ] Document backup/restore procedures
  - [ ] Document monitoring setup
  - [ ] Document incident response
  - [ ] Document user management

- [ ] **Compliance documentation**
  - [ ] Document HIPAA compliance measures
  - [ ] Create audit log retention policy
  - [ ] Document data encryption methods
  - [ ] Create security incident response plan
  - [ ] Document access control policies

### Training

- [ ] **User training**
  - [ ] Train researchers on query interface
  - [ ] Train on dataset export
  - [ ] Train on data interpretation
  - [ ] Provide query examples
  - [ ] Create video tutorials

- [ ] **Admin training**
  - [ ] Train on user management
  - [ ] Train on monitoring
  - [ ] Train on troubleshooting
  - [ ] Train on backup/restore
  - [ ] Train on incident response

## Ongoing Maintenance

### Daily

- [ ] Check system health
- [ ] Review error logs
- [ ] Monitor performance metrics
- [ ] Check backup completion

### Weekly

- [ ] Review audit logs
- [ ] Check disk space
- [ ] Review security alerts
- [ ] Update documentation as needed

### Monthly

- [ ] Review and rotate logs
- [ ] Test backup restoration
- [ ] Review user access
- [ ] Update dependencies
- [ ] Security patch updates

### Quarterly

- [ ] Security audit
- [ ] Performance review
- [ ] Capacity planning
- [ ] User feedback review
- [ ] Feature prioritization

### Annually

- [ ] Compliance audit
- [ ] Disaster recovery drill
- [ ] Security penetration testing
- [ ] Infrastructure review
- [ ] Cost optimization review

## HIPAA Compliance Checklist

- [ ] **Administrative Safeguards**
  - [ ] Security management process documented
  - [ ] Assigned security responsibility
  - [ ] Workforce security policies
  - [ ] Information access management
  - [ ] Security awareness training
  - [ ] Security incident procedures
  - [ ] Contingency plan
  - [ ] Business associate agreements

- [ ] **Physical Safeguards**
  - [ ] Facility access controls
  - [ ] Workstation use policies
  - [ ] Workstation security
  - [ ] Device and media controls

- [ ] **Technical Safeguards**
  - [ ] Access control (unique user IDs, emergency access)
  - [ ] Audit controls (audit logs with 7-year retention)
  - [ ] Integrity controls (data integrity verification)
  - [ ] Person or entity authentication
  - [ ] Transmission security (encryption in transit)

- [ ] **Documentation**
  - [ ] Policies and procedures documented
  - [ ] Changes documented
  - [ ] Retention period defined (6 years minimum)
  - [ ] Documentation available to workforce

## Rollback Plan

In case of deployment issues:

1. **Immediate rollback**
   ```bash
   # Revert to previous Docker image
   docker-compose down
   docker-compose up -d --build previous-version
   ```

2. **Database rollback**
   ```bash
   # Restore from backup
   pg_restore -d research_dataset_builder backup.sql
   ```

3. **Verify rollback**
   - Check health endpoint
   - Test login
   - Test query submission
   - Verify data integrity

4. **Communicate**
   - Notify users of rollback
   - Document issues encountered
   - Plan fix and redeployment

## Emergency Contacts

- **System Administrator**: [Name, Phone, Email]
- **Database Administrator**: [Name, Phone, Email]
- **Security Officer**: [Name, Phone, Email]
- **On-Call Developer**: [Name, Phone, Email]
- **Hosting Provider Support**: [Phone, Email]
- **LLM API Support**: [OpenAI/Anthropic Support]

## Sign-Off

- [ ] **Development Lead**: _________________ Date: _______
- [ ] **Security Officer**: _________________ Date: _______
- [ ] **Database Administrator**: _________________ Date: _______
- [ ] **System Administrator**: _________________ Date: _______
- [ ] **Project Manager**: _________________ Date: _______
- [ ] **Compliance Officer**: _________________ Date: _______

---

**Deployment Date**: _________________

**Deployed By**: _________________

**Deployment Notes**:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
