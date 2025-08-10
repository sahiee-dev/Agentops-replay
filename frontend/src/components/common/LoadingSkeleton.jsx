import React from 'react';
import Skeleton from 'react-loading-skeleton';
import 'react-loading-skeleton/dist/skeleton.css';

const LoadingSkeleton = () => {
    return (
        <div className="loading-skeleton">
            {/* Header skeleton */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <Skeleton height={40} width={200} />
                    <Skeleton height={20} width={300} style={{ marginTop: '8px' }} />
                </div>
                <Skeleton height={45} width={120} />
            </div>

            {/* Stats cards skeleton */}
            <div className="row mb-4">
                {[1, 2, 3, 4].map((item) => (
                    <div key={item} className="col-md-3">
                        <div className="card">
                            <div className="card-body text-center">
                                <Skeleton height={60} width={60} circle style={{ margin: '0 auto 16px' }} />
                                <Skeleton height={32} width={80} style={{ margin: '0 auto 8px' }} />
                                <Skeleton height={16} width={120} style={{ margin: '0 auto' }} />
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Table skeleton */}
            <div className="card">
                <div className="card-header">
                    <Skeleton height={24} width={150} />
                </div>
                <div className="card-body">
                    <div className="table-responsive">
                        <table className="table">
                            <thead>
                                <tr>
                                    {[1, 2, 3, 4, 5].map((col) => (
                                        <th key={col}>
                                            <Skeleton height={20} />
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {[1, 2, 3, 4, 5].map((row) => (
                                    <tr key={row}>
                                        {[1, 2, 3, 4, 5].map((col) => (
                                            <td key={col}>
                                                <Skeleton height={20} />
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default LoadingSkeleton;
