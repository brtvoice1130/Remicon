import React, { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import * as XLSX from 'xlsx';

// API URL 설정 - 환경변수 사용
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [settings, setSettings] = useState(() => {
    // localStorage에서 저장된 프롬프트 불러오기
    const savedPrompt = localStorage.getItem('data_extraction_prompt');
    return {
      prompt: savedPrompt || "모든 페이지에서 거래 데이터를 추출하여 현장명과 공급자명을 정확히 식별하고, 소계/합계 행은 제외해주세요."
    };
  });
  const [search, setSearch] = useState("");
  const [notification, setNotification] = useState(null);
  const [savedData, setSavedData] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [extractedData, setExtractedData] = useState([]);
  const [debugInfo, setDebugInfo] = useState(null);
  const [showResults, setShowResults] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showPromptModal, setShowPromptModal] = useState(false);
  const [logs, setLogs] = useState([]);
  const [retryCount, setRetryCount] = useState(0);
  const [isOfflineMode, setIsOfflineMode] = useState(false);
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  const addLog = (message, type = "info") => {
    const timestamp = new Date().toLocaleTimeString();
    const uniqueId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}-${performance.now()}`;
    const newLog = { timestamp, message, type, id: uniqueId };
    setLogs(prev => [newLog, ...prev].slice(0, 100));
  };

  const showNotification = useCallback((message, type = "success") => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
  }, []);

  // 프롬프트 저장 함수
  const savePrompt = useCallback((newPrompt) => {
    localStorage.setItem('data_extraction_prompt', newPrompt);
    addLog(`💾 프롬프트 저장됨: ${newPrompt.substring(0, 30)}...`, "info");
    showNotification("프롬프트가 저장되었습니다.", "success");
  }, [addLog, showNotification]);

  // 엑셀 다운로드 함수
  const downloadExcel = useCallback((data, filename = "추출결과") => {
    try {
      if (!data || data.length === 0) {
        showNotification("다운로드할 데이터가 없습니다.", "warning");
        return;
      }

      // 데이터를 엑셀 형식에 맞게 변환
      const excelData = data.map((item, index) => ({
        '순번': index + 1,
        '거래(출하)일': item.출하일 || item.delivery_date || '-',
        '현장명(대기업소)': item.현장명 || item.site_name || '-',
        '공급자(상호)': item.공급자 || item.supplier || '-',
        '품목': item.품명 || item.item_name || '-',
        '규격': item.규격 || item.specification || '-',
        '단위': item.단위 || item.unit || 'M3',
        '물량(수량)': item.물량 || item.quantity || 0,
        '단가': item.단가 || item.unit_price || 0,
        '금액(공급가액)': item.공급가액 || item.amount || 0,
        '세액': item.세액 || item.tax_amount || 0,
        '합계': item.합계 || item.total_amount || 0,
        '통화': 'KRW'
      }));

      // 워크북 생성
      const ws = XLSX.utils.json_to_sheet(excelData);
      const wb = XLSX.utils.book_new();

      // 컬럼 폭 설정
      const colWidths = [
        {wch: 6},   // 순번
        {wch: 12},  // 납세(출하일)
        {wch: 25},  // 현장명(대기업소)
        {wch: 20},  // 공급자(상호)
        {wch: 15},  // 품목
        {wch: 15},  // 규격
        {wch: 8},   // 단위
        {wch: 12},  // 물량
        {wch: 12},  // 단가
        {wch: 15},  // 금액(공급가액)
        {wch: 12},  // 세액
        {wch: 15},  // 합계
        {wch: 8}    // 통화
      ];
      ws['!cols'] = colWidths;

      // 워크시트 추가
      XLSX.utils.book_append_sheet(wb, ws, '추출 결과');

      // 파일명 생성 (현재 날짜와 시간 포함)
      const now = new Date();
      const dateStr = now.toISOString().slice(0, 19).replace(/[:-]/g, '').replace('T', '_');
      const finalFilename = `${filename}_${dateStr}.xlsx`;

      // 다운로드 실행
      XLSX.writeFile(wb, finalFilename);

      addLog(`📥 엑셀 파일 다운로드: ${finalFilename}`, "success");
      showNotification(`엑셀 파일이 다운로드되었습니다: ${finalFilename}`, "success");
    } catch (error) {
      console.error("Excel download error:", error);
      addLog(`❌ 엑셀 다운로드 실패: ${error.message}`, "error");
      showNotification("엑셀 다운로드 중 오류가 발생했습니다.", "error");
    }
  }, [showNotification, addLog]);

  // 앱 시작시 API 연결 테스트
  useEffect(() => {
    const testApiConnection = async () => {
      try {
        addLog(`🚀 앱 시작 - API 연결 테스트`);
        const response = await axios.get(`${API_BASE_URL}/`, { timeout: 5000 });

        if (response.data.status === 'healthy') {
          addLog(`✅ API 서버 연결 성공`, "success");
          addLog(`💾 데이터베이스: ${response.data.database}`, "info");
          addLog(`🔗 API: ${response.data.ai_api}`, "info");
          fetchSavedData();
          fetchStatistics();
        } else {
          addLog(`⚠️ API 응답이 올바르지 않음`, "warning");
        }
      } catch (error) {
        addLog(`❌ API 연결 실패: ${error.message}`, "error");
        setError("API 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.");
      }
    };

    testApiConnection();

    // 네트워크 상태 감지
    const handleOnline = () => {
      setIsOnline(true);
      addLog("🌐 네트워크 연결이 복원되었습니다", "success");
      showNotification("네트워크가 연결되었습니다.", "success");
    };

    const handleOffline = () => {
      setIsOnline(false);
      addLog("📡 네트워크 연결이 끊어졌습니다", "warning");
      showNotification("네트워크 연결을 확인해주세요.", "warning");
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const fetchSavedData = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/data/`);
      setSavedData(response.data.data || []);
    } catch (error) {
      addLog(`❌ 저장된 데이터 로드 실패: ${error.message}`, "error");
    }
  };

  const fetchStatistics = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/statistics/`);
      setStatistics(response.data.statistics || {});
    } catch (error) {
      addLog(`❌ 통계 데이터 로드 실패: ${error.message}`, "error");
    }
  };

  const handleFileChange = (e) => {
    if (loading) {
      return; // 로딩 중에는 파일 변경 불가
    }

    const selectedFile = e.target.files[0];
    setFile(selectedFile);
    setResult(null);
    setError("");
    setExtractedData([]);
    setDebugInfo(null);
    setShowResults(false);

    if (selectedFile) {
      addLog(`📄 파일 선택됨: ${selectedFile.name} (${(selectedFile.size / 1024).toFixed(1)}KB)`);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError("PDF 파일을 선택해주세요.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    setExtractedData([]);
    setDebugInfo(null);
    setShowResults(false);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("prompt", settings.prompt || "");

    try {
      addLog(`🚀 PDF 업로드 시작: ${file.name}`);
      addLog(`📝 추출 지시사항: ${settings.prompt.substring(0, 50)}...`);

      const response = await axios.post(`${API_BASE_URL}/upload_pdf/`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000,
      });

      addLog(`📨 서버 응답 수신: ${response.status}`);

      if (response.data.status === 'success') {
        setResult(response.data);
        setExtractedData(response.data.ai_raw_extraction || []);
        setDebugInfo(response.data.debug_info);
        setShowResults(true);

        addLog(`✅ PDF 처리 완료: ${response.data.extraction_details?.total_extracted || 0}개 데이터 추출`, "success");
        showNotification(`성공적으로 처리되었습니다! ${response.data.saved_count || 0}개 데이터가 저장되었습니다.`, "success");

        fetchSavedData();
        fetchStatistics();
      } else if (response.data.status === 'api_quota_exceeded') {
        const quotaMessage = `API 할당량이 소진되었습니다. ${response.data.recovery_time}에 자동으로 복원됩니다.`;
        setError(quotaMessage);
        addLog(`⏰ API 할당량 소진: ${response.data.recovery_time}에 재시도`, "warning");
        showNotification(quotaMessage, "warning");

        // 오프라인 모드 제안
        if (retryCount < 3) {
          setIsOfflineMode(true);
        }
      } else {
        setError(response.data.error || "처리 중 오류가 발생했습니다.");
        addLog(`❌ 처리 실패: ${response.data.error}`, "error");
        showNotification("처리 중 오류가 발생했습니다.", "error");
      }
    } catch (error) {
      console.error("Upload error:", error);

      if (error.response && error.response.status === 429) {
        const quotaMessage = "API 사용량이 일시적으로 제한되었습니다. 잠시 후 다시 시도해주세요.";
        setError(quotaMessage);
        addLog(`⏰ API 제한: 429 Too Many Requests`, "warning");
        showNotification(quotaMessage, "warning");
        setRetryCount(prev => prev + 1);
        setIsOfflineMode(true);
      } else {
        const errorMessage = error.response?.data?.message || error.message || "알 수 없는 오류가 발생했습니다.";
        setError("서버 오류가 발생했습니다: " + errorMessage);
        addLog(`❌ 업로드 오류: ${errorMessage}`, "error");
        showNotification("업로드 중 오류가 발생했습니다.", "error");
      }
    } finally {
      setLoading(false);
    }
  };

  const deleteData = async (id) => {
    try {
      await axios.delete(`${API_BASE_URL}/data/${id}`);
      showNotification("데이터가 삭제되었습니다.", "success");
      fetchSavedData();
      fetchStatistics();
    } catch (error) {
      showNotification("삭제 중 오류가 발생했습니다.", "error");
    }
  };

  const clearAllData = async () => {
    if (window.confirm("모든 데이터를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.")) {
      try {
        await axios.delete(`${API_BASE_URL}/data/`);
        showNotification("모든 데이터가 삭제되었습니다.", "success");
        fetchSavedData();
        fetchStatistics();
      } catch (error) {
        showNotification("삭제 중 오류가 발생했습니다.", "error");
      }
    }
  };

  const filteredData = useMemo(() => {
    return savedData.filter(item =>
      Object.values(item).some(value =>
        value && value.toString().toLowerCase().includes(search.toLowerCase())
      )
    );
  }, [savedData, search]);

  // 업체별 합계 계산
  const companyTotals = useMemo(() => {
    const currentData = (extractedData && extractedData.length > 0) ? extractedData : filteredData;
    if (!currentData || currentData.length === 0) return [];

    const companyMap = new Map();

    currentData.forEach(item => {
      const company = item.공급자 || item.supplier || '미분류';
      const amount = item.합계 || item.total_amount || item.공급가액 || item.amount || 0;
      const quantity = item.물량 || item.quantity || 0;

      if (companyMap.has(company)) {
        const existing = companyMap.get(company);
        companyMap.set(company, {
          company: company,
          count: existing.count + 1,
          totalAmount: existing.totalAmount + amount,
          totalQuantity: existing.totalQuantity + quantity
        });
      } else {
        companyMap.set(company, {
          company: company,
          count: 1,
          totalAmount: amount,
          totalQuantity: quantity
        });
      }
    });

    return Array.from(companyMap.values()).sort((a, b) => b.totalAmount - a.totalAmount);
  }, [extractedData, filteredData]);

  // 모달 열림/닫힘에 따른 배경 스크롤 제어
  useEffect(() => {
    if (showPromptModal) {
      document.body.classList.add('modal-open');
    } else {
      document.body.classList.remove('modal-open');
    }

    // 컴포넌트 언마운트 시 클래스 제거
    return () => {
      document.body.classList.remove('modal-open');
    };
  }, [showPromptModal]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 노션 스타일 헤더 */}
      <header>
        <div className="header-container">
          <div className="header-flex">
            <div className="header-left">
              <div className="logo">
                <span>R</span>
              </div>
              <div>
                <h1 className="header-title">Document Analytics</h1>
                <p className="header-subtitle">PDF 데이터 추출 플랫폼</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {statistics && (
                <div className="stats-container">
                  <span>📊 {statistics.total_records}개 레코드</span>
                  <span>📁 {statistics.total_files}개 파일</span>
                  <span>💰 ₩{statistics.total_amount?.toLocaleString() || 0}</span>
                </div>
              )}

              {/* 네트워크 상태 표시 */}
              <div className="flex items-center gap-2">
                {!isOnline && (
                  <span className="text-sm text-red-600 bg-red-50 px-2 py-1 rounded" title="오프라인">
                    📡 오프라인
                  </span>
                )}
                {isOfflineMode && (
                  <span className="text-sm text-yellow-600 bg-yellow-50 px-2 py-1 rounded" title="API 제한">
                    ⏰ API 제한
                  </span>
                )}
              </div>

              <button
                onClick={() => setShowSettings(!showSettings)}
                className="settings-btn"
                title="설정"
              >
                ⚙️
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="main-container">
        {/* PDF 업로드 영역 - 상단 배치 */}
        <div className="space-y-6">
          {/* PDF 업로드 섹션 */}
          <div className="notion-card">
            <div className="card-header">
              <div className="card-icon green-bg">
                <span>📄</span>
              </div>
              <div className="flex-1">
                <h2 className="card-title">PDF 문서 업로드</h2>
                <p className="card-subtitle">거래명세서를 업로드하여 데이터를 추출하세요</p>
              </div>
              <div className="flex items-center gap-3 ml-auto">
                <button
                  type="button"
                  onClick={() => setShowPromptModal(true)}
                  className="btn-small secondary"
                  title="추출 지침 설정"
                >
                  📝 지침 설정
                </button>
              </div>
            </div>


            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="form-group">
                <label className="form-label">
                  PDF 파일 선택
                </label>
                <div className="file-upload-area">
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={handleFileChange}
                    className="file-upload-input"
                    id="file-upload"
                    disabled={loading}
                  />
                  <label htmlFor="file-upload" className="upload-content">
                    {file ? (
                      <>
                        <span>📄</span>
                        <span className="font-medium">{file.name}</span>
                        <span className="text-gray-500">({(file.size / 1024).toFixed(1)}KB)</span>
                      </>
                    ) : (
                      <>
                        <span className="upload-icon">📁</span>
                        <span className="upload-text">클릭하여 PDF 파일을 선택하세요</span>
                      </>
                    )}
                  </label>
                </div>
              </div>

              <button
                type="submit"
                disabled={!file || loading}
                className={`btn ${!file || loading ? "" : "btn-primary"}`}
              >
                {loading ? (
                  <>
                    <div className="spinner"></div>
                    <span>분석 중...</span>
                  </>
                ) : (
                  "📊 데이터 추출하기"
                )}
              </button>
            </form>

            {error && (
              <div className="error-message">
                <div className="error-content">
                  <span className="error-icon">⚠️</span>
                  <div className="error-text">
                    <p className="error-title">오류 발생</p>
                    <p className="error-description">{error}</p>

                    {isOfflineMode && (
                      <div className="error-actions">
                        <button
                          onClick={() => {
                            setError("");
                            setIsOfflineMode(false);
                            setRetryCount(0);
                            addLog("🔄 사용자가 재시도를 요청했습니다", "info");
                          }}
                          className="btn-small primary"
                        >
                          🔄 다시 시도
                        </button>
                        <button
                          onClick={() => {
                            window.open('https://console.cloud.google.com/', '_blank');
                            addLog("🌐 Google Cloud Console 열기", "info");
                          }}
                          className="btn-small secondary"
                        >
                          🛠️ API 설정 확인
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 메인 데이터 테이블 - 항상 표시 */}
          <div className="notion-card">
            <div className="card-header">
              <div className="card-icon blue-bg">
                <span>📊</span>
              </div>
              <div className="flex-1">
                <h2 className="card-title">거래 데이터</h2>
                <p className="card-subtitle">
                  {(extractedData && extractedData.length > 0)
                    ? `${extractedData.length}개의 추출된 데이터`
                    : (filteredData && filteredData.length > 0)
                    ? `${filteredData.length}개의 저장된 데이터`
                    : "데이터가 없습니다"
                  }
                </p>
              </div>
              <div className="flex items-center gap-3 ml-auto">
                <div className="text-center">
                  <div className="text-sm text-gray-500">
                    {showResults ? "추출 시간" : "최종 업데이트"}
                  </div>
                  <div className="text-sm font-mono text-gray-700">
                    {showResults && result?.extraction_details?.extraction_time ?
                      new Date(result.extraction_details.extraction_time).toLocaleString() :
                      new Date().toLocaleString()
                    }
                  </div>
                </div>
                <button
                  onClick={() => {
                    const dataToDownload = (extractedData && extractedData.length > 0) ? extractedData : filteredData;
                    if (dataToDownload && dataToDownload.length > 0) {
                      downloadExcel(dataToDownload, "거래데이터");
                    }
                  }}
                  disabled={!((extractedData && extractedData.length > 0) || (filteredData && filteredData.length > 0))}
                  className={`btn-small ${((extractedData && extractedData.length > 0) || (filteredData && filteredData.length > 0)) ? 'primary' : 'disabled'}`}
                  title="엑셀로 다운로드"
                >
                  📥 엑셀 다운로드
                </button>
              </div>
            </div>

            {/* 메인 데이터 테이블 */}
            <div className="results-table-container">
              <div className="table-container">
                <table className="results-table">
                  <thead>
                    <tr>
                      <th>순번</th>
                      <th>거래(출하)일</th>
                      <th>현장명(대기업소)</th>
                      <th>공급자(상호)</th>
                      <th>품목</th>
                      <th>규격</th>
                      <th>단위</th>
                      <th>물량(수량)</th>
                      <th>단가</th>
                      <th>금액(공급가액)</th>
                      <th>세액</th>
                      <th>합계</th>
                      <th>통화</th>
                    </tr>
                  </thead>
                  <tbody>
                    {/* 추출된 데이터 우선 표시 */}
                    {(extractedData && extractedData.length > 0) ? (
                      extractedData.map((item, index) => (
                        <tr key={`extracted-row-${index}-${item.출하일 || 'no-date'}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`}>
                          <td className="text-center font-medium">{index + 1}</td>
                          <td className="text-center">{item.출하일 || '-'}</td>
                          <td className="text-left">{item.현장명 || '-'}</td>
                          <td className="text-left">{item.공급자 || '-'}</td>
                          <td className="text-left">{item.품명 || '-'}</td>
                          <td className="text-center">{item.규격 || '-'}</td>
                          <td className="text-center">{item.단위 || 'M3'}</td>
                          <td className="text-right">{item.물량 ? item.물량.toLocaleString() : '-'}</td>
                          <td className="text-right">{item.단가 ? item.단가.toLocaleString() : '-'}</td>
                          <td className="text-right font-medium">{item.공급가액 ? item.공급가액.toLocaleString() : '-'}</td>
                          <td className="text-right">{item.세액 ? item.세액.toLocaleString() : '-'}</td>
                          <td className="text-right font-semibold">{item.합계 ? item.합계.toLocaleString() : '-'}</td>
                          <td className="text-center">KRW</td>
                        </tr>
                      ))
                    ) : (filteredData && filteredData.length > 0) ? (
                      filteredData.map((item, index) => (
                        <tr key={`saved-main-row-${item.id}-${index}-${Date.now()}`}>
                          <td className="text-center font-medium">{index + 1}</td>
                          <td className="text-center">{item.delivery_date ? new Date(item.delivery_date).toLocaleDateString() : '-'}</td>
                          <td className="text-left">{item.site_name || '-'}</td>
                          <td className="text-left">{item.supplier || '-'}</td>
                          <td className="text-left">{item.item_name || '-'}</td>
                          <td className="text-center">{item.specification || '-'}</td>
                          <td className="text-center">{item.unit || 'M3'}</td>
                          <td className="text-right">{item.quantity ? item.quantity.toLocaleString() : '-'}</td>
                          <td className="text-right">{item.unit_price ? item.unit_price.toLocaleString() : '-'}</td>
                          <td className="text-right font-medium">{item.amount ? item.amount.toLocaleString() : '-'}</td>
                          <td className="text-right">{item.tax_amount ? item.tax_amount.toLocaleString() : '-'}</td>
                          <td className="text-right font-semibold">{item.total_amount ? item.total_amount.toLocaleString() : '-'}</td>
                          <td className="text-center">KRW</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan="13" className="text-center py-12 text-gray-500">
                          <div className="empty-state">
                            <span className="empty-state-icon">📊</span>
                            <p className="empty-state-title">거래 데이터가 없습니다</p>
                            <p className="empty-state-subtitle">PDF를 업로드하여 데이터를 추출해보세요</p>
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* 요약 정보 */}
              {((extractedData && extractedData.length > 0) || (filteredData && filteredData.length > 0)) && (
                <div className="results-summary">
                  <div className="summary-item">
                    <span className="summary-label">총 레코드:</span>
                    <span className="summary-value">
                      {(extractedData && extractedData.length > 0) ? extractedData.length : filteredData.length}개
                    </span>
                  </div>
                  <div className="summary-item">
                    <span className="summary-label">총 금액:</span>
                    <span className="summary-value">
                      ₩{(extractedData && extractedData.length > 0)
                        ? extractedData.reduce((sum, item) => sum + (item.합계 || item.공급가액 || 0), 0).toLocaleString()
                        : filteredData.reduce((sum, item) => sum + (item.total_amount || item.amount || 0), 0).toLocaleString()
                      }
                    </span>
                  </div>
                  <div className="summary-item">
                    <span className="summary-label">총 물량:</span>
                    <span className="summary-value">
                      {(extractedData && extractedData.length > 0)
                        ? extractedData.reduce((sum, item) => sum + (item.물량 || 0), 0).toLocaleString()
                        : filteredData.reduce((sum, item) => sum + (item.quantity || 0), 0).toLocaleString()
                      } M3
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 업체별 합계 섹션 */}
          {companyTotals.length > 0 && (
            <div className="notion-card">
              <div className="card-header">
                <div className="card-icon purple-bg">
                  <span>🏢</span>
                </div>
                <div className="flex-1">
                  <h2 className="card-title">업체별 합계</h2>
                  <p className="card-subtitle">공급업체별 거래 현황 및 합계 정보</p>
                </div>
              </div>

              <div className="company-totals-grid">
                {companyTotals.map((company, index) => (
                  <div key={`company-${index}-${company.company}`} className="company-total-card">
                    <div className="company-name">
                      <span className="company-icon">🏭</span>
                      <span className="company-text">{company.company}</span>
                    </div>
                    <div className="company-stats">
                      <div className="stat-item">
                        <span className="stat-label">거래건수</span>
                        <span className="stat-value">{company.count.toLocaleString()}건</span>
                      </div>
                      <div className="stat-item">
                        <span className="stat-label">총 물량</span>
                        <span className="stat-value">{company.totalQuantity.toLocaleString()} M3</span>
                      </div>
                      <div className="stat-item">
                        <span className="stat-label">총 금액</span>
                        <span className="stat-value">₩{company.totalAmount.toLocaleString()}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 설정 섹션 */}
          {showSettings && (
            <div className="notion-card">
              <div className="card-header">
                <div className="card-icon gray-bg">
                  <span>⚙️</span>
                </div>
                <h3 className="card-title">고급 설정</h3>
              </div>

              <div className="space-y-4">
                <div className="text-center py-4 text-gray-500">
                  추가 설정 옵션이 여기에 표시됩니다.
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 노티피케이션 */}
      {notification && (
        <div className={`notification ${notification.type}`}>
          <div className="notification-content">
            <span className="notification-icon">
              {notification.type === "success" ? "✅" :
               notification.type === "warning" ? "⚠️" : "❌"}
            </span>
            <span className="notification-text">{notification.message}</span>
          </div>
        </div>
      )}

      {/* 지침설정 모달 */}
      {showPromptModal && (
        <div className="modal-overlay" onClick={() => setShowPromptModal(false)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-icon">
                <span>📝</span>
              </div>
              <div className="modal-title-section">
                <h3 className="modal-title">추출 지침 설정</h3>
                <p className="modal-subtitle">데이터 추출 시 사용할 지시사항을 설정하세요</p>
              </div>
              <button
                onClick={() => setShowPromptModal(false)}
                className="modal-close-btn"
                title="닫기"
              >
                ✖️
              </button>
            </div>

            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">
                  지시사항
                </label>
                <textarea
                  value={settings.prompt}
                  onChange={(e) => setSettings(prev => ({ ...prev, prompt: e.target.value }))}
                  className="textarea modal-textarea"
                  placeholder="데이터를 추출할 때 사용할 지시사항을 입력하세요"
                  rows="6"
                />
              </div>
            </div>

            <div className="modal-footer">
              <button
                onClick={() => setShowPromptModal(false)}
                className="btn-small secondary"
              >
                취소
              </button>
              <button
                onClick={() => {
                  savePrompt(settings.prompt);
                  setShowPromptModal(false);
                }}
                className="btn-small primary"
              >
                💾 저장 후 닫기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;