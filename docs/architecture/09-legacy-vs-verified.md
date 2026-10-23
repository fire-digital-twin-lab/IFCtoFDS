# 09 — Quick và Verified

| Nội dung | Quick Preview | Verified Conversion |
| --- | --- | --- |
| Implementation | JavaScript trong frontend/engines/legacy | Python application + modules |
| Preview | web-ifc hoặc parser legacy theo đường hiện tại | Geometry preview backend, chưa có acceptance |
| Chuyển đổi | Parser/exporter và worker trình duyệt | IfcOpenShell, mapping plan, serializer, audit nguồn độc lập |
| Kết luận | Không tự gắn verified | Phụ thuộc gates và evidence |
| Chạy trực tiếp file | Có, dùng inline workers | Cần HTTP backend |

Không hợp nhất hai thuật toán trong lần refactor này. Đổi giao diện không chuyển quyền quyết định mapping/acceptance từ backend sang component. Preview hoặc tạo FDS thành công không phải bằng chứng nghiệm thu. Không tự suy airflow, fan curve, sprinkler hoặc CO-device physics từ sự hiện diện của phần tử IFC.
