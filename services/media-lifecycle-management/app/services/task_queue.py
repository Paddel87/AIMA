#!/usr/bin/env python3
"""
Task Queue Service for the AIMA Media Lifecycle Management Service.

This module provides a comprehensive task queue system for managing
asynchronous media processing tasks, job scheduling, and workflow orchestration.
"""

import logging
import asyncio
import json
from typing import Any, Dict, List, Optional, Callable, Union, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from uuid import UUID, uuid4
import traceback
from concurrent.futures import ThreadPoolExecutor
import pickle
import time

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update, delete
from sqlalchemy.orm import selectinload

from ..core.database import ProcessingJob, MediaFile
from ..core.redis_client import CacheManager
from ..middleware.error_handling import MediaProcessingError
from .audit_service import AuditService, AuditEventType, AuditSeverity
from .notification_service import NotificationService
from .monitoring_service import MonitoringService


logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    SCHEDULED = "scheduled"


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class QueueType(str, Enum):
    """Different types of task queues."""
    DEFAULT = "default"
    MEDIA_PROCESSING = "media_processing"
    THUMBNAIL_GENERATION = "thumbnail_generation"
    TRANSCODING = "transcoding"
    METADATA_EXTRACTION = "metadata_extraction"
    BACKUP = "backup"
    CLEANUP = "cleanup"
    NOTIFICATION = "notification"
    ANALYTICS = "analytics"


@dataclass
class TaskResult:
    """Result of task execution."""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TaskContext:
    """Context information for task execution."""
    task_id: UUID
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    request_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Task:
    """Represents a task in the queue."""
    id: UUID
    name: str
    function: str  # Function name or path
    args: List[Any]
    kwargs: Dict[str, Any]
    queue: QueueType
    priority: TaskPriority
    status: TaskStatus
    context: TaskContext
    
    # Scheduling
    scheduled_at: Optional[datetime] = None
    execute_at: Optional[datetime] = None
    
    # Retry configuration
    max_retries: int = 3
    retry_count: int = 0
    retry_delay: float = 60.0  # seconds
    exponential_backoff: bool = True
    
    # Execution tracking
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None
    
    # Results
    result: Optional[TaskResult] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    
    # Dependencies
    depends_on: Optional[List[UUID]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.execute_at is None:
            self.execute_at = self.scheduled_at or datetime.utcnow()


@dataclass
class QueueStats:
    """Statistics for a queue."""
    queue_name: str
    pending_count: int
    running_count: int
    completed_count: int
    failed_count: int
    total_count: int
    avg_execution_time: Optional[float] = None
    last_processed: Optional[datetime] = None


class TaskRegistry:
    """Registry for task functions."""
    
    def __init__(self):
        self._tasks: Dict[str, Callable] = {}
    
    def register(self, name: str, func: Callable):
        """Register a task function."""
        self._tasks[name] = func
        logger.info(f"Registered task function: {name}")
    
    def get(self, name: str) -> Optional[Callable]:
        """Get a registered task function."""
        return self._tasks.get(name)
    
    def list_tasks(self) -> List[str]:
        """List all registered task names."""
        return list(self._tasks.keys())
    
    def decorator(self, name: Optional[str] = None):
        """Decorator for registering task functions."""
        def wrapper(func: Callable):
            task_name = name or func.__name__
            self.register(task_name, func)
            return func
        return wrapper


class TaskQueue:
    """Main task queue service."""
    
    def __init__(
        self,
        cache_manager: CacheManager,
        audit_service: Optional[AuditService] = None,
        notification_service: Optional[NotificationService] = None,
        monitoring_service: Optional[MonitoringService] = None
    ):
        self.cache = cache_manager
        self.audit_service = audit_service
        self.notification_service = notification_service
        self.monitoring_service = monitoring_service
        
        # Task registry
        self.registry = TaskRegistry()
        
        # Configuration
        self.max_workers = 10
        self.max_queue_size = 1000
        self.task_timeout = 3600  # 1 hour
        self.cleanup_interval = 300  # 5 minutes
        self.stats_interval = 60  # 1 minute
        
        # Runtime state
        self._running = False
        self._workers: List[asyncio.Task] = []
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._cleanup_task: Optional[asyncio.Task] = None
        self._stats_task: Optional[asyncio.Task] = None
        
        # Queue management
        self._queues: Dict[QueueType, asyncio.Queue] = {}
        self._queue_stats: Dict[QueueType, QueueStats] = {}
        
        # Initialize queues
        self._initialize_queues()
    
    def _initialize_queues(self):
        """Initialize task queues."""
        for queue_type in QueueType:
            self._queues[queue_type] = asyncio.Queue(maxsize=self.max_queue_size)
            self._queue_stats[queue_type] = QueueStats(
                queue_name=queue_type.value,
                pending_count=0,
                running_count=0,
                completed_count=0,
                failed_count=0,
                total_count=0
            )
        
        logger.info(f"Initialized {len(self._queues)} task queues")
    
    async def start(self):
        """Start the task queue service."""
        if self._running:
            logger.warning("Task queue is already running")
            return
        
        self._running = True
        
        # Start worker tasks
        for i in range(self.max_workers):
            worker_task = asyncio.create_task(
                self._worker(f"worker-{i}"),
                name=f"task-queue-worker-{i}"
            )
            self._workers.append(worker_task)
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(),
            name="task-queue-cleanup"
        )
        
        # Start stats task
        self._stats_task = asyncio.create_task(
            self._stats_loop(),
            name="task-queue-stats"
        )
        
        logger.info(f"Task queue started with {self.max_workers} workers")
    
    async def stop(self):
        """Stop the task queue service."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel all workers
        for worker in self._workers:
            worker.cancel()
        
        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        # Cancel cleanup and stats tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._stats_task:
            self._stats_task.cancel()
        
        # Shutdown executor
        self._executor.shutdown(wait=True)
        
        self._workers.clear()
        logger.info("Task queue stopped")
    
    async def submit_task(
        self,
        db: AsyncSession,
        name: str,
        function: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        queue: QueueType = QueueType.DEFAULT,
        priority: TaskPriority = TaskPriority.NORMAL,
        context: Optional[TaskContext] = None,
        scheduled_at: Optional[datetime] = None,
        max_retries: int = 3,
        retry_delay: float = 60.0,
        depends_on: Optional[List[UUID]] = None
    ) -> UUID:
        """
        Submit a task to the queue.
        
        Args:
            db: Database session
            name: Task name
            function: Function name to execute
            args: Function arguments
            kwargs: Function keyword arguments
            queue: Queue to submit to
            priority: Task priority
            context: Task context
            scheduled_at: When to execute the task
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries
            depends_on: Task dependencies
        
        Returns:
            Task ID
        """
        task_id = uuid4()
        
        # Create task context if not provided
        if context is None:
            context = TaskContext(task_id=task_id)
        else:
            context.task_id = task_id
        
        # Create task
        task = Task(
            id=task_id,
            name=name,
            function=function,
            args=args or [],
            kwargs=kwargs or {},
            queue=queue,
            priority=priority,
            status=TaskStatus.PENDING if scheduled_at is None else TaskStatus.SCHEDULED,
            context=context,
            scheduled_at=scheduled_at,
            max_retries=max_retries,
            retry_delay=retry_delay,
            depends_on=depends_on
        )
        
        # Store task in cache
        await self._store_task(task)
        
        # Add to queue if not scheduled
        if scheduled_at is None or scheduled_at <= datetime.utcnow():
            await self._enqueue_task(task)
        
        # Update statistics
        self._queue_stats[queue].total_count += 1
        self._queue_stats[queue].pending_count += 1
        
        # Log task submission
        if self.audit_service:
            from .audit_service import AuditContext, AuditEvent
            
            audit_context = AuditContext(
                user_id=context.user_id,
                session_id=context.session_id,
                correlation_id=context.correlation_id
            )
            
            audit_event = AuditEvent(
                event_type=AuditEventType.PROCESSING_JOB_CREATED,
                severity=AuditSeverity.LOW,
                status="success",
                message=f"Task submitted: {name}",
                context=audit_context,
                details={
                    "task_id": str(task_id),
                    "function": function,
                    "queue": queue.value,
                    "priority": priority.value,
                    "scheduled_at": scheduled_at.isoformat() if scheduled_at else None
                }
            )
            
            await self.audit_service.log_event(db, audit_event)
        
        logger.info(f"Task submitted: {name} ({task_id}) to queue {queue.value}")
        return task_id
    
    async def get_task(self, task_id: UUID) -> Optional[Task]:
        """Get task by ID."""
        try:
            cache_key = f"task:{task_id}"
            task_data = await self.cache.get(cache_key)
            
            if task_data:
                # Deserialize task
                return self._deserialize_task(task_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            return None
    
    async def cancel_task(self, db: AsyncSession, task_id: UUID) -> bool:
        """Cancel a task."""
        try:
            task = await self.get_task(task_id)
            if not task:
                return False
            
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return False
            
            # Update task status
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            
            # Store updated task
            await self._store_task(task)
            
            # Update statistics
            self._queue_stats[task.queue].pending_count = max(0, self._queue_stats[task.queue].pending_count - 1)
            
            # Log cancellation
            if self.audit_service:
                from .audit_service import AuditContext, AuditEvent
                
                audit_context = AuditContext(
                    user_id=task.context.user_id,
                    session_id=task.context.session_id,
                    correlation_id=task.context.correlation_id
                )
                
                audit_event = AuditEvent(
                    event_type=AuditEventType.PROCESSING_JOB_CANCELLED,
                    severity=AuditSeverity.MEDIUM,
                    status="success",
                    message=f"Task cancelled: {task.name}",
                    context=audit_context,
                    details={"task_id": str(task_id)}
                )
                
                await self.audit_service.log_event(db, audit_event)
            
            logger.info(f"Task cancelled: {task.name} ({task_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {e}")
            return False
    
    async def retry_task(self, db: AsyncSession, task_id: UUID) -> bool:
        """Retry a failed task."""
        try:
            task = await self.get_task(task_id)
            if not task or task.status != TaskStatus.FAILED:
                return False
            
            if task.retry_count >= task.max_retries:
                logger.warning(f"Task {task_id} has exceeded max retries")
                return False
            
            # Reset task for retry
            task.status = TaskStatus.PENDING
            task.retry_count += 1
            task.started_at = None
            task.completed_at = None
            task.execution_time = None
            task.error_message = None
            task.error_traceback = None
            
            # Calculate retry delay with exponential backoff
            if task.exponential_backoff:
                delay = task.retry_delay * (2 ** (task.retry_count - 1))
            else:
                delay = task.retry_delay
            
            task.execute_at = datetime.utcnow() + timedelta(seconds=delay)
            
            # Store updated task
            await self._store_task(task)
            
            # Re-enqueue task
            await self._enqueue_task(task)
            
            # Update statistics
            self._queue_stats[task.queue].pending_count += 1
            self._queue_stats[task.queue].failed_count = max(0, self._queue_stats[task.queue].failed_count - 1)
            
            logger.info(f"Task retried: {task.name} ({task_id}), attempt {task.retry_count}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to retry task {task_id}: {e}")
            return False
    
    async def get_queue_stats(self, queue: Optional[QueueType] = None) -> Union[QueueStats, Dict[QueueType, QueueStats]]:
        """Get queue statistics."""
        if queue:
            return self._queue_stats.get(queue)
        return dict(self._queue_stats)
    
    async def list_tasks(
        self,
        queue: Optional[QueueType] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Task]:
        """List tasks with optional filtering."""
        try:
            # Get all task keys from cache
            pattern = "task:*"
            task_keys = await self.cache.scan_keys(pattern)
            
            tasks = []
            for key in task_keys[offset:offset + limit]:
                task_data = await self.cache.get(key)
                if task_data:
                    task = self._deserialize_task(task_data)
                    
                    # Apply filters
                    if queue and task.queue != queue:
                        continue
                    if status and task.status != status:
                        continue
                    
                    tasks.append(task)
            
            # Sort by created_at descending
            tasks.sort(key=lambda t: t.created_at or datetime.min, reverse=True)
            
            return tasks
            
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            return []
    
    async def _worker(self, worker_name: str):
        """Worker coroutine that processes tasks."""
        logger.info(f"Worker {worker_name} started")
        
        while self._running:
            try:
                # Get task from highest priority queue
                task = await self._get_next_task()
                
                if task:
                    await self._execute_task(task, worker_name)
                else:
                    # No tasks available, wait a bit
                    await asyncio.sleep(1)
                    
            except asyncio.CancelledError:
                logger.info(f"Worker {worker_name} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
                await asyncio.sleep(5)  # Wait before retrying
        
        logger.info(f"Worker {worker_name} stopped")
    
    async def _get_next_task(self) -> Optional[Task]:
        """Get the next task to execute based on priority."""
        # Priority order
        priority_order = [
            TaskPriority.CRITICAL,
            TaskPriority.URGENT,
            TaskPriority.HIGH,
            TaskPriority.NORMAL,
            TaskPriority.LOW
        ]
        
        # Check each queue in priority order
        for queue_type in QueueType:
            queue = self._queues[queue_type]
            
            if not queue.empty():
                try:
                    # Get task with timeout
                    task = await asyncio.wait_for(queue.get(), timeout=0.1)
                    
                    # Check if task is ready to execute
                    if task.execute_at and task.execute_at > datetime.utcnow():
                        # Task is scheduled for later, put it back
                        await queue.put(task)
                        continue
                    
                    # Check dependencies
                    if task.depends_on:
                        dependencies_met = await self._check_dependencies(task.depends_on)
                        if not dependencies_met:
                            # Dependencies not met, put task back
                            await queue.put(task)
                            continue
                    
                    return task
                    
                except asyncio.TimeoutError:
                    continue
        
        return None
    
    async def _check_dependencies(self, dependency_ids: List[UUID]) -> bool:
        """Check if all task dependencies are completed."""
        for dep_id in dependency_ids:
            dep_task = await self.get_task(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True
    
    async def _execute_task(self, task: Task, worker_name: str):
        """Execute a single task."""
        start_time = time.time()
        
        try:
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            await self._store_task(task)
            
            # Update statistics
            self._queue_stats[task.queue].pending_count = max(0, self._queue_stats[task.queue].pending_count - 1)
            self._queue_stats[task.queue].running_count += 1
            
            logger.info(f"Worker {worker_name} executing task: {task.name} ({task.id})")
            
            # Get task function
            func = self.registry.get(task.function)
            if not func:
                raise MediaProcessingError(f"Task function not found: {task.function}")
            
            # Execute task
            if asyncio.iscoroutinefunction(func):
                # Async function
                result = await asyncio.wait_for(
                    func(*task.args, **task.kwargs),
                    timeout=self.task_timeout
                )
            else:
                # Sync function - run in executor
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        self._executor,
                        func,
                        *task.args,
                        **task.kwargs
                    ),
                    timeout=self.task_timeout
                )
            
            # Task completed successfully
            execution_time = time.time() - start_time
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.execution_time = execution_time
            task.result = TaskResult(
                success=True,
                result=result,
                execution_time=execution_time
            )
            
            # Update statistics
            self._queue_stats[task.queue].running_count = max(0, self._queue_stats[task.queue].running_count - 1)
            self._queue_stats[task.queue].completed_count += 1
            self._queue_stats[task.queue].last_processed = datetime.utcnow()
            
            # Update average execution time
            stats = self._queue_stats[task.queue]
            if stats.avg_execution_time is None:
                stats.avg_execution_time = execution_time
            else:
                stats.avg_execution_time = (stats.avg_execution_time + execution_time) / 2
            
            logger.info(f"Task completed: {task.name} ({task.id}) in {execution_time:.2f}s")
            
        except asyncio.TimeoutError:
            # Task timed out
            execution_time = time.time() - start_time
            error_msg = f"Task timed out after {self.task_timeout}s"
            
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.execution_time = execution_time
            task.error_message = error_msg
            task.result = TaskResult(
                success=False,
                error=error_msg,
                execution_time=execution_time
            )
            
            # Update statistics
            self._queue_stats[task.queue].running_count = max(0, self._queue_stats[task.queue].running_count - 1)
            self._queue_stats[task.queue].failed_count += 1
            
            logger.error(f"Task timed out: {task.name} ({task.id})")
            
        except Exception as e:
            # Task failed
            execution_time = time.time() - start_time
            error_msg = str(e)
            error_traceback = traceback.format_exc()
            
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.execution_time = execution_time
            task.error_message = error_msg
            task.error_traceback = error_traceback
            task.result = TaskResult(
                success=False,
                error=error_msg,
                execution_time=execution_time
            )
            
            # Update statistics
            self._queue_stats[task.queue].running_count = max(0, self._queue_stats[task.queue].running_count - 1)
            self._queue_stats[task.queue].failed_count += 1
            
            logger.error(f"Task failed: {task.name} ({task.id}): {error_msg}")
            
            # Check if task should be retried
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.RETRYING
                
                # Calculate retry delay
                if task.exponential_backoff:
                    delay = task.retry_delay * (2 ** task.retry_count)
                else:
                    delay = task.retry_delay
                
                task.execute_at = datetime.utcnow() + timedelta(seconds=delay)
                task.retry_count += 1
                
                # Re-enqueue for retry
                await self._enqueue_task(task)
                
                logger.info(f"Task scheduled for retry: {task.name} ({task.id}), attempt {task.retry_count}")
        
        finally:
            # Store final task state
            await self._store_task(task)
            
            # Send notifications if configured
            if self.notification_service and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                await self._send_task_notification(task)
    
    async def _send_task_notification(self, task: Task):
        """Send notification about task completion/failure."""
        try:
            if task.context.user_id:
                if task.status == TaskStatus.COMPLETED:
                    await self.notification_service.send_task_completed_notification(
                        user_id=task.context.user_id,
                        task_name=task.name,
                        task_id=task.id,
                        execution_time=task.execution_time
                    )
                elif task.status == TaskStatus.FAILED:
                    await self.notification_service.send_task_failed_notification(
                        user_id=task.context.user_id,
                        task_name=task.name,
                        task_id=task.id,
                        error_message=task.error_message
                    )
        except Exception as e:
            logger.warning(f"Failed to send task notification: {e}")
    
    async def _enqueue_task(self, task: Task):
        """Add task to appropriate queue."""
        try:
            queue = self._queues[task.queue]
            await queue.put(task)
        except Exception as e:
            logger.error(f"Failed to enqueue task {task.id}: {e}")
    
    async def _store_task(self, task: Task):
        """Store task in cache."""
        try:
            cache_key = f"task:{task.id}"
            task_data = self._serialize_task(task)
            
            # Store with TTL (tasks expire after 7 days)
            await self.cache.set(cache_key, task_data, ttl=7 * 24 * 3600)
            
        except Exception as e:
            logger.error(f"Failed to store task {task.id}: {e}")
    
    def _serialize_task(self, task: Task) -> Dict[str, Any]:
        """Serialize task to dictionary."""
        task_dict = asdict(task)
        
        # Convert datetime objects to ISO strings
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            return obj
        
        return convert_datetime(task_dict)
    
    def _deserialize_task(self, task_data: Dict[str, Any]) -> Task:
        """Deserialize task from dictionary."""
        # Convert ISO strings back to datetime objects
        def convert_datetime(obj):
            if isinstance(obj, str):
                try:
                    return datetime.fromisoformat(obj)
                except ValueError:
                    return obj
            elif isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            return obj
        
        converted_data = convert_datetime(task_data)
        
        # Convert enum strings back to enums
        if 'queue' in converted_data:
            converted_data['queue'] = QueueType(converted_data['queue'])
        if 'priority' in converted_data:
            converted_data['priority'] = TaskPriority(converted_data['priority'])
        if 'status' in converted_data:
            converted_data['status'] = TaskStatus(converted_data['status'])
        
        # Convert UUIDs
        if 'id' in converted_data:
            converted_data['id'] = UUID(converted_data['id'])
        if 'depends_on' in converted_data and converted_data['depends_on']:
            converted_data['depends_on'] = [UUID(dep_id) for dep_id in converted_data['depends_on']]
        
        # Reconstruct nested objects
        if 'context' in converted_data:
            context_data = converted_data['context']
            if 'task_id' in context_data:
                context_data['task_id'] = UUID(context_data['task_id'])
            if 'user_id' in context_data and context_data['user_id']:
                context_data['user_id'] = UUID(context_data['user_id'])
            converted_data['context'] = TaskContext(**context_data)
        
        if 'result' in converted_data and converted_data['result']:
            converted_data['result'] = TaskResult(**converted_data['result'])
        
        return Task(**converted_data)
    
    async def _cleanup_loop(self):
        """Cleanup loop for removing old completed tasks."""
        while self._running:
            try:
                await self._cleanup_old_tasks()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
                await asyncio.sleep(60)
    
    async def _cleanup_old_tasks(self):
        """Remove old completed/failed tasks."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=7)
            
            # Get all task keys
            pattern = "task:*"
            task_keys = await self.cache.scan_keys(pattern)
            
            cleaned_count = 0
            for key in task_keys:
                task_data = await self.cache.get(key)
                if task_data:
                    task = self._deserialize_task(task_data)
                    
                    # Remove old completed/failed tasks
                    if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] and
                        task.completed_at and task.completed_at < cutoff_time):
                        
                        await self.cache.delete(key)
                        cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old tasks")
                
        except Exception as e:
            logger.error(f"Task cleanup failed: {e}")
    
    async def _stats_loop(self):
        """Statistics collection loop."""
        while self._running:
            try:
                await self._update_queue_stats()
                await asyncio.sleep(self.stats_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stats loop error: {e}")
                await asyncio.sleep(60)
    
    async def _update_queue_stats(self):
        """Update queue statistics."""
        try:
            # Reset counters
            for stats in self._queue_stats.values():
                stats.pending_count = 0
                stats.running_count = 0
                stats.completed_count = 0
                stats.failed_count = 0
            
            # Count tasks by status
            pattern = "task:*"
            task_keys = await self.cache.scan_keys(pattern)
            
            for key in task_keys:
                task_data = await self.cache.get(key)
                if task_data:
                    task = self._deserialize_task(task_data)
                    stats = self._queue_stats[task.queue]
                    
                    if task.status == TaskStatus.PENDING:
                        stats.pending_count += 1
                    elif task.status == TaskStatus.RUNNING:
                        stats.running_count += 1
                    elif task.status == TaskStatus.COMPLETED:
                        stats.completed_count += 1
                    elif task.status == TaskStatus.FAILED:
                        stats.failed_count += 1
            
            # Report metrics to monitoring service
            if self.monitoring_service:
                for queue_type, stats in self._queue_stats.items():
                    await self.monitoring_service.record_metric(
                        f"task_queue.{queue_type.value}.pending",
                        stats.pending_count
                    )
                    await self.monitoring_service.record_metric(
                        f"task_queue.{queue_type.value}.running",
                        stats.running_count
                    )
                    await self.monitoring_service.record_metric(
                        f"task_queue.{queue_type.value}.completed",
                        stats.completed_count
                    )
                    await self.monitoring_service.record_metric(
                        f"task_queue.{queue_type.value}.failed",
                        stats.failed_count
                    )
                    
                    if stats.avg_execution_time:
                        await self.monitoring_service.record_metric(
                            f"task_queue.{queue_type.value}.avg_execution_time",
                            stats.avg_execution_time
                        )
            
        except Exception as e:
            logger.error(f"Stats update failed: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of the task queue service."""
        try:
            stats = await self.get_queue_stats()
            
            total_pending = sum(s.pending_count for s in stats.values())
            total_running = sum(s.running_count for s in stats.values())
            total_completed = sum(s.completed_count for s in stats.values())
            total_failed = sum(s.failed_count for s in stats.values())
            
            return {
                "status": "healthy" if self._running else "stopped",
                "running": self._running,
                "workers": len(self._workers),
                "max_workers": self.max_workers,
                "registered_tasks": len(self.registry.list_tasks()),
                "queue_stats": {
                    "total_pending": total_pending,
                    "total_running": total_running,
                    "total_completed": total_completed,
                    "total_failed": total_failed
                },
                "queues": {q.value: asdict(s) for q, s in stats.items()},
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global task registry and queue instances
task_registry = TaskRegistry()


def task(name: Optional[str] = None, queue: QueueType = QueueType.DEFAULT):
    """Decorator for registering task functions."""
    def wrapper(func: Callable):
        task_name = name or func.__name__
        task_registry.register(task_name, func)
        
        # Add metadata to function
        func._task_name = task_name
        func._task_queue = queue
        
        return func
    return wrapper


def get_task_registry() -> TaskRegistry:
    """Get the global task registry."""
    return task_registry