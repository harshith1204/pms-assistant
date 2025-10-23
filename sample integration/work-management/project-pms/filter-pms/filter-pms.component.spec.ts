import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FilterPmsComponent } from './filter-pms.component';

describe('FilterPmsComponent', () => {
  let component: FilterPmsComponent;
  let fixture: ComponentFixture<FilterPmsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ FilterPmsComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(FilterPmsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
